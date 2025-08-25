"""
Core YokedCache implementation.

This module contains the main YokedCache class that provides the primary
caching functionality, including Redis integration, auto-invalidation,
and cache management operations.
"""

import asyncio
import inspect
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Union

try:
    import redis.asyncio as redis
    from redis.asyncio.connection import ConnectionPool

    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore
    ConnectionPool = None  # type: ignore
    REDIS_AVAILABLE = False

from .circuit_breaker import CircuitBreaker, CircuitBreakerError, RetryWithBackoff
from .config import CacheConfig
from .exceptions import (
    CacheConnectionError,
    CacheInvalidationError,
    CacheKeyError,
    CacheSerializationError,
    CacheTimeoutError,
    YokedCacheError,
)
from .metrics import CacheMetrics, OperationMetric, get_global_metrics
from .models import (
    CacheEntry,
    CacheStats,
    FuzzySearchResult,
    InvalidationRule,
    InvalidationType,
    SerializationMethod,
    TableCacheConfig,
)
from .utils import (
    calculate_ttl_with_jitter,
    deserialize_data,
    extract_table_from_query,
    generate_cache_key,
    get_current_timestamp,
    get_operation_type_from_query,
    normalize_tags,
    sanitize_key,
    serialize_data,
)

logger = logging.getLogger(__name__)


class YokedCache:
    """
    Main caching class that provides intelligent caching with Redis backend.

    Features:
    - Automatic cache invalidation based on database operations
    - Variable TTLs per table/query type
    - Tag-based cache grouping and invalidation
    - Fuzzy search capabilities
    - Performance metrics and monitoring
    - Async/await support for FastAPI integration
    """

    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        redis_url: Optional[str] = None,
        config_file: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Initialize YokedCache.

        Args:
            config: CacheConfig instance
            redis_url: Redis connection URL (overrides config)
            config_file: Path to configuration file
            **kwargs: Additional configuration parameters to override
        """
        # Load configuration
        if config:
            self.config = config
        elif config_file:
            from .config import load_config_from_file

            self.config = load_config_from_file(config_file)
        else:
            self.config = CacheConfig()

        # Override Redis URL if provided
        if redis_url:
            self.config.redis_url = redis_url

        # Apply any additional keyword arguments to override config
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                logger.warning(f"Unknown configuration parameter: {key}")

        # Initialize Redis connection
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None

        # Cache statistics
        self._stats = CacheStats()
        self._start_time = time.time()

        # Internal state
        self._connected = False
        self._shutdown = False

        # Error handling and resilience
        if self.config.enable_circuit_breaker:
            self._circuit_breaker: Optional[CircuitBreaker] = CircuitBreaker(
                failure_threshold=self.config.circuit_breaker_failure_threshold,
                timeout=self.config.circuit_breaker_timeout,
                expected_exception=(
                    CacheConnectionError,
                    CacheTimeoutError,
                    redis.ConnectionError,
                    redis.TimeoutError,
                    Exception,  # Catch-all for Redis exceptions
                ),
            )
        else:
            self._circuit_breaker = None

        # Retry mechanism
        self._retry_handler = RetryWithBackoff(
            max_retries=self.config.connection_retries,
            base_delay=self.config.retry_delay,
        )

        # Metrics collection
        if self.config.enable_metrics:
            self._metrics: Optional[CacheMetrics] = CacheMetrics()
        else:
            self._metrics = None

        # Setup logging
        self._setup_logging()

    def _is_running_in_async_context(self) -> bool:
        """Check if we're currently running in an async context."""
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            return loop is not None
        except RuntimeError:
            # No event loop running
            return False

    def _warn_sync_in_async(self, method_name: str) -> None:
        """Warn when sync methods are called in async contexts."""
        if self._is_running_in_async_context():
            frame = inspect.currentframe()
            if frame and frame.f_back and frame.f_back.f_back:
                caller_frame = frame.f_back.f_back
                filename = caller_frame.f_code.co_filename
                lineno = caller_frame.f_lineno
                logger.warning(
                    f"Sync method '{method_name}' called from async context at {filename}:{lineno}. "
                    f"Consider using 'a{method_name}' for better performance."
                )

    async def _sync_fallback(self, coro_func, *args, **kwargs):
        """Execute async function in sync context with proper error handling."""
        try:
            if self._is_running_in_async_context():
                # We're already in an async context, just await
                return await coro_func(*args, **kwargs)
            else:
                # We're in sync context, create new event loop
                return asyncio.run(coro_func(*args, **kwargs))
        except Exception as e:
            if self.config.fallback_enabled:
                logger.warning(f"Cache operation failed, returning None: {e}")
                return None
            raise

    def _setup_logging(self) -> None:
        """Configure logging based on configuration."""
        logger.setLevel(getattr(logging, self.config.log_level.upper(), logging.INFO))

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._connected:
            return

        try:
            # Create connection pool with full configuration
            pool_config = self.config.get_connection_pool_config()
            self._pool = ConnectionPool.from_url(self.config.redis_url, **pool_config)

            # Create Redis client
            self._redis = redis.Redis(connection_pool=self._pool)

            # Test connection
            await self._redis.ping()

            self._connected = True
            logger.info("Connected to Redis successfully")

        except Exception as e:
            self._connected = False
            raise CacheConnectionError(
                f"Failed to connect to Redis: {e}",
                {"redis_url": self.config.redis_url, "error": str(e)},
            )

    async def disconnect(self) -> None:
        """Close Redis connection."""
        self._shutdown = True

        if self._redis:
            # Use aclose() if available (Redis 5.0+), otherwise use close()
            if hasattr(self._redis, "aclose"):
                await self._redis.aclose()
            else:
                await self._redis.close()

        if self._pool:
            await self._pool.disconnect()

        self._connected = False
        logger.info("Disconnected from Redis")

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        if not self._connected or not self._redis:
            return False

        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    async def detailed_health_check(self) -> Dict[str, Any]:
        """
        Comprehensive health check for monitoring.

        Returns detailed information about cache health, performance,
        and system status suitable for monitoring dashboards.
        """
        health_info: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache": {
                "connected": self._connected,
                "redis_available": False,
                "connection_pool_stats": None,
                "circuit_breaker_stats": None,
            },
            "performance": {
                "total_operations": 0,
                "hit_rate": 0.0,
                "average_response_time_ms": 0.0,
            },
            "errors": [],
            "warnings": [],
        }

        # Test Redis connectivity
        try:
            if self._redis:
                start_time = time.time()
                await self._redis.ping()
                ping_time = (time.time() - start_time) * 1000
                health_info["cache"]["redis_available"] = True
                health_info["cache"]["ping_time_ms"] = round(ping_time, 2)
            else:
                health_info["cache"]["redis_available"] = False
                health_info["errors"].append("Redis client not initialized")
        except Exception as e:
            health_info["cache"]["redis_available"] = False
            health_info["errors"].append(f"Redis connection failed: {str(e)}")
            health_info["status"] = "unhealthy"

        # Get connection pool stats
        try:
            if self._pool:
                pool_stats = {
                    "max_connections": self.config.max_connections,
                    "created_connections": getattr(
                        self._pool, "created_connections", 0
                    ),
                    "available_connections": getattr(
                        self._pool, "available_connections", 0
                    ),
                    "in_use_connections": getattr(self._pool, "in_use_connections", 0),
                }
                health_info["cache"]["connection_pool_stats"] = pool_stats

                # Check for connection pool issues
                in_use_ratio = (
                    pool_stats.get("in_use_connections", 0)
                    / pool_stats["max_connections"]
                )
                if in_use_ratio > 0.8:
                    health_info["warnings"].append(
                        f"High connection pool usage: {in_use_ratio:.1%}"
                    )
        except Exception as e:
            health_info["warnings"].append(
                f"Could not get connection pool stats: {str(e)}"
            )

        # Get circuit breaker stats
        if self._circuit_breaker:
            try:
                cb_stats = self._circuit_breaker.get_stats()
                health_info["cache"]["circuit_breaker_stats"] = cb_stats

                if cb_stats["state"] == "open":
                    health_info["status"] = "degraded"
                    health_info["errors"].append("Circuit breaker is open")
                elif cb_stats["failure_rate"] > 0.1:  # 10% failure rate
                    health_info["warnings"].append(
                        f"High failure rate: {cb_stats['failure_rate']:.1%}"
                    )
            except Exception as e:
                health_info["warnings"].append(
                    f"Could not get circuit breaker stats: {str(e)}"
                )

        # Get performance stats
        try:
            stats = await self.get_stats()
            health_info["performance"]["total_operations"] = (
                stats.total_hits
                + stats.total_misses
                + stats.total_sets
                + stats.total_deletes
            )
            health_info["performance"]["hit_rate"] = stats.hit_rate
            health_info["performance"]["total_keys"] = stats.total_keys
            health_info["performance"]["memory_usage_mb"] = round(
                stats.total_memory_bytes / (1024 * 1024), 2
            )
            health_info["performance"]["uptime_seconds"] = stats.uptime_seconds

            # Performance warnings
            if stats.hit_rate < 50.0:  # Less than 50% hit rate
                health_info["warnings"].append(f"Low hit rate: {stats.hit_rate:.1f}%")

        except Exception as e:
            health_info["warnings"].append(f"Could not get performance stats: {str(e)}")

        # Test basic operations
        try:
            test_key = f"health_check_{int(time.time())}"
            test_value = "health_check_value"

            # Test set operation
            start_time = time.time()
            set_result = await self.set(test_key, test_value, ttl=60)
            set_time = (time.time() - start_time) * 1000

            if not set_result:
                health_info["errors"].append("Failed to set test key")
                health_info["status"] = "unhealthy"

            # Test get operation
            start_time = time.time()
            get_result = await self.get(test_key)
            get_time = (time.time() - start_time) * 1000

            if get_result != test_value:
                health_info["errors"].append("Failed to retrieve test key")
                health_info["status"] = "unhealthy"

            # Test delete operation
            start_time = time.time()
            delete_result = await self.delete(test_key)
            delete_time = (time.time() - start_time) * 1000

            if not delete_result:
                health_info["warnings"].append("Failed to delete test key")

            # Average operation time
            avg_time = (set_time + get_time + delete_time) / 3
            health_info["performance"]["average_response_time_ms"] = round(avg_time, 2)

            # Performance warnings
            if avg_time > 100:  # Slower than 100ms
                health_info["warnings"].append(
                    f"Slow operations: {avg_time:.1f}ms average"
                )

        except Exception as e:
            health_info["errors"].append(f"Operation test failed: {str(e)}")
            health_info["status"] = "unhealthy"

        # Determine overall status
        if health_info["errors"]:
            health_info["status"] = "unhealthy"
        elif health_info["warnings"]:
            if health_info["status"] == "healthy":
                health_info["status"] = "degraded"

        return health_info

    @asynccontextmanager
    async def _get_redis(self) -> AsyncGenerator[redis.Redis, None]:
        """Get Redis client with automatic connection management."""
        if not self._connected:
            await self.connect()

        if not self._redis:
            raise CacheConnectionError("Redis client not available")

        yield self._redis

    def _record_operation_metric(
        self,
        operation_type: str,
        key: str,
        duration_ms: float,
        success: bool,
        error_type: Optional[str] = None,
        cache_hit: Optional[bool] = None,
        table: Optional[str] = None,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Record an operation metric if metrics are enabled."""
        if self._metrics:
            metric = OperationMetric(
                operation_type=operation_type,
                key=key,
                duration_ms=duration_ms,
                success=success,
                error_type=error_type,
                cache_hit=cache_hit,
                table=table,
                tags=tags or set(),
            )
            self._metrics.record_operation(metric)

    async def _execute_with_resilience(
        self, operation: Callable, *args, **kwargs
    ) -> Any:
        """Execute Redis operation with circuit breaker and retry logic."""

        async def _execute():
            if self._circuit_breaker:
                return await self._circuit_breaker.call_async(
                    operation, *args, **kwargs
                )
            else:
                return await operation(*args, **kwargs)

        try:
            if self.config.connection_retries > 0:
                return await self._retry_handler.execute_async(_execute)
            else:
                return await _execute()

        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker prevented operation: {e}")
            if self.config.fallback_enabled:
                return None
            raise
        except Exception as e:
            logger.error(f"Redis operation failed: {e}")
            if self.config.fallback_enabled:
                return None
            raise

    async def get(
        self,
        key: str,
        default: Any = None,
        touch: bool = True,
    ) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if key not found
            touch: Whether to update access time and hit count

        Returns:
            Cached value or default
        """
        sanitized_key = self._build_key(key)
        start_time = time.time()
        cache_hit = False
        success = False
        error_type = None

        try:

            async def _get_operation():
                nonlocal cache_hit

                async with self._get_redis() as r:
                    # Get value from Redis
                    data = await r.get(sanitized_key)

                    if data is None:
                        self._stats.add_miss()
                        if self.config.log_cache_misses:
                            logger.debug(f"Cache miss: {sanitized_key}")
                        cache_hit = False
                        return default

                    # Deserialize value
                    try:
                        value = deserialize_data(data, SerializationMethod.JSON)
                    except CacheSerializationError:
                        # Try pickle as fallback
                        try:
                            value = deserialize_data(data, SerializationMethod.PICKLE)
                        except CacheSerializationError:
                            logger.warning(
                                f"Failed to deserialize data for key: {sanitized_key}"
                            )
                            return default

                    # Update statistics
                    self._stats.add_hit()
                    cache_hit = True

                    # Update access time if requested
                    if touch:
                        try:
                            await r.touch(sanitized_key)
                        except Exception:
                            # touch command might not be supported (e.g., in fakeredis)
                            pass

                    if self.config.log_cache_hits:
                        logger.debug(f"Cache hit: {sanitized_key}")

                    return value

            result = await self._execute_with_resilience(_get_operation)
            success = True
            return result if result is not None else default

        except Exception as e:
            error_type = type(e).__name__
            raise
        finally:
            # Record metrics
            duration_ms = (time.time() - start_time) * 1000
            self._record_operation_metric(
                operation_type="get",
                key=sanitized_key,
                duration_ms=duration_ms,
                success=success,
                error_type=error_type,
                cache_hit=cache_hit,
            )

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Union[str, List[str], Set[str]]] = None,
        serialization: Optional[SerializationMethod] = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Tags for grouping and invalidation
            serialization: Serialization method to use

        Returns:
            True if successful, False otherwise
        """
        sanitized_key = self._build_key(key)
        actual_ttl = ttl or self.config.default_ttl
        actual_ttl = calculate_ttl_with_jitter(actual_ttl)
        serialization = serialization or self.config.default_serialization

        start_time = time.time()
        success = False
        error_type = None
        normalized_tags = normalize_tags(tags) if tags else set()

        try:

            async def _set_operation():
                # Serialize value
                serialized_data = serialize_data(value, serialization)

                async with self._get_redis() as r:
                    # Start pipeline for atomic operations
                    async with r.pipeline() as pipe:
                        # Set the main key
                        await pipe.setex(sanitized_key, actual_ttl, serialized_data)

                        # Handle tags
                        if tags:
                            await self._add_tags_to_key(
                                pipe, sanitized_key, normalized_tags, actual_ttl
                            )

                        # Execute pipeline
                        await pipe.execute()

                self._stats.total_sets += 1
                logger.debug(f"Cache set: {sanitized_key} (TTL: {actual_ttl}s)")
                return True

            result = await self._execute_with_resilience(_set_operation)
            success = result is not None and result
            return result if result is not None else False

        except Exception as e:
            error_type = type(e).__name__
            raise
        finally:
            # Record metrics
            duration_ms = (time.time() - start_time) * 1000
            self._record_operation_metric(
                operation_type="set",
                key=sanitized_key,
                duration_ms=duration_ms,
                success=success,
                error_type=error_type,
                tags=normalized_tags,
            )

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if key didn't exist
        """
        sanitized_key = self._build_key(key)

        try:
            async with self._get_redis() as r:
                result = await r.delete(sanitized_key)

                if result > 0:
                    self._stats.total_deletes += 1
                    logger.debug(f"Cache delete: {sanitized_key}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error deleting cache key {sanitized_key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        sanitized_key = self._build_key(key)

        try:
            async with self._get_redis() as r:
                result = await r.exists(sanitized_key)
                return result > 0
        except Exception as e:
            logger.error(f"Error checking key existence {sanitized_key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for existing key."""
        sanitized_key = self._build_key(key)

        try:
            async with self._get_redis() as r:
                result = await r.expire(sanitized_key, ttl)
                return result
        except Exception as e:
            logger.error(f"Error setting expiration for key {sanitized_key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Redis pattern (supports * and ? wildcards)

        Returns:
            Number of keys invalidated
        """
        full_pattern = self._build_key(pattern)

        try:
            async with self._get_redis() as r:
                # Find matching keys
                keys = await r.keys(full_pattern)

                if not keys:
                    return 0

                # Delete all matching keys
                deleted = await r.delete(*keys)

                self._stats.total_invalidations += deleted
                logger.info(f"Invalidated {deleted} keys matching pattern: {pattern}")

                return deleted

        except Exception as e:
            logger.error(f"Error invalidating pattern {pattern}: {e}")
            raise CacheInvalidationError(pattern, "pattern", {"error": str(e)})

    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        """
        Invalidate all keys associated with given tags.

        Args:
            tags: Tags to invalidate

        Returns:
            Number of keys invalidated
        """
        normalized_tags = normalize_tags(tags)
        total_invalidated = 0

        try:
            async with self._get_redis() as r:
                for tag in normalized_tags:
                    tag_key = self._build_tag_key(tag)

                    # Get all keys for this tag
                    keys = await r.smembers(tag_key)

                    if keys:
                        # Delete the actual cache keys
                        deleted = await r.delete(*keys)
                        total_invalidated += deleted

                        # Clean up the tag set
                        await r.delete(tag_key)

                self._stats.total_invalidations += total_invalidated
                logger.info(
                    f"Invalidated {total_invalidated} keys for tags: {list(normalized_tags)}"
                )

                return total_invalidated

        except Exception as e:
            logger.error(f"Error invalidating tags {list(normalized_tags)}: {e}")
            raise CacheInvalidationError(
                str(normalized_tags), "tags", {"error": str(e)}
            )

    async def flush_all(self) -> bool:
        """
        Flush all cache keys with the configured prefix.

        Returns:
            True if successful
        """
        try:
            async with self._get_redis() as r:
                # Get all keys with our prefix
                pattern = self._build_key("*")
                keys = await r.keys(pattern)

                if not keys:
                    deleted = 0
                else:
                    # Delete all matching keys
                    deleted = await r.delete(*keys)
                    self._stats.total_invalidations += deleted

                logger.warning(f"Flushed all cache keys ({deleted} keys deleted)")
                return True

        except Exception as e:
            logger.error(f"Error flushing cache: {e}")
            return False

    async def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        # Update uptime
        self._stats.uptime_seconds = time.time() - self._start_time

        # Get Redis memory info if available
        try:
            async with self._get_redis() as r:
                info = await r.info("memory")
                self._stats.total_memory_bytes = info.get("used_memory", 0)

                # Get total keys count
                info_keyspace = await r.info("keyspace")
                db_info = info_keyspace.get(f"db{self.config.redis_db}", {})
                if isinstance(db_info, dict):
                    self._stats.total_keys = db_info.get("keys", 0)

        except Exception as e:
            logger.debug(f"Could not get Redis stats: {e}")

        return self._stats

    async def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics including enhanced performance data."""
        if self._metrics:
            return self._metrics.get_comprehensive_stats()
        else:
            # Fall back to basic stats if metrics not enabled
            stats = await self.get_stats()
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics_enabled": False,
                "basic_stats": {
                    "total_hits": stats.total_hits,
                    "total_misses": stats.total_misses,
                    "total_sets": stats.total_sets,
                    "total_deletes": stats.total_deletes,
                    "hit_rate": stats.hit_rate,
                    "total_keys": stats.total_keys,
                    "uptime_seconds": stats.uptime_seconds,
                },
            }

    def start_metrics_collection(self) -> None:
        """Start background metrics collection if enabled."""
        if self._metrics and self.config.enable_metrics:
            asyncio.create_task(
                self._metrics.start_background_collection(
                    interval_seconds=self.config.metrics_interval
                )
            )

    async def stop_metrics_collection(self) -> None:
        """Stop background metrics collection."""
        if self._metrics:
            await self._metrics.stop_background_collection()

    async def fuzzy_search(
        self,
        query: str,
        threshold: int = 80,
        max_results: int = 10,
        tags: Optional[Set[str]] = None,
    ) -> List[FuzzySearchResult]:
        """
        Perform fuzzy search on cached data.

        Args:
            query: Search query
            threshold: Similarity threshold (0-100)
            max_results: Maximum number of results
            tags: Optional tags to filter by

        Returns:
            List of fuzzy search results
        """
        if not self.config.enable_fuzzy:
            logger.warning("Fuzzy search is disabled in configuration")
            return []

        threshold = threshold or self.config.fuzzy_threshold
        max_results = max_results or self.config.fuzzy_max_results

        try:
            # Import fuzzy matching library
            from fuzzywuzzy import fuzz, process
        except ImportError:
            logger.error("fuzzywuzzy library not available for fuzzy search")
            return []

        results: List[FuzzySearchResult] = []

        try:
            async with self._get_redis() as r:
                # Get keys to search
                if tags:
                    # Search within tagged keys
                    search_keys_set = set()
                    for tag in tags:
                        tag_key = self._build_tag_key(tag)
                        tag_keys = await r.smembers(tag_key)
                        search_keys_set.update(tag_keys)
                    search_keys = list(search_keys_set)
                else:
                    # Search all keys with our prefix
                    pattern = self._build_key("*")
                    search_keys = await r.keys(pattern)

                if not search_keys:
                    return results

                # Convert byte keys to strings for fuzzy matching
                key_strings = [
                    key.decode() if isinstance(key, bytes) else str(key)
                    for key in search_keys
                ]

                # Perform fuzzy matching
                matches = process.extract(
                    query, key_strings, scorer=fuzz.partial_ratio, limit=max_results
                )

                # Get values for matching keys
                for match_result in matches:
                    if len(match_result) >= 2:
                        matched_key, score = match_result[0], match_result[1]
                    else:
                        continue
                    if score >= threshold:
                        try:
                            value = await self.get(matched_key, touch=False)
                            if value is not None:
                                # Create cache entry
                                cache_entry = CacheEntry(
                                    key=matched_key,
                                    value=value,
                                    created_at=datetime.now(timezone.utc),
                                )

                                # Create fuzzy search result
                                result = FuzzySearchResult(
                                    key=matched_key,
                                    value=value,
                                    score=score,
                                    matched_term=query,
                                    cache_entry=cache_entry,
                                )
                                results.append(result)
                        except Exception as e:
                            logger.debug(
                                f"Error getting fuzzy match value for {matched_key}: {e}"
                            )

                logger.debug(
                    f"Fuzzy search for '{query}' returned {len(results)} results"
                )

        except Exception as e:
            logger.error(f"Error in fuzzy search: {e}")

        return results

    def _build_key(self, key: str) -> str:
        """Build full cache key with prefix."""
        # Check if key already has the full prefix with separator
        expected_prefix = f"{self.config.key_prefix}:"
        if key.startswith(expected_prefix):
            return sanitize_key(key)
        return sanitize_key(f"{self.config.key_prefix}:{key}")

    def _build_tag_key(self, tag: str) -> str:
        """Build tag key for storing key sets."""
        return self._build_key(f"tags:{tag}")

    async def _add_tags_to_key(
        self, pipe: redis.Redis, key: str, tags: Set[str], ttl: int
    ) -> None:
        """Add key to tag sets."""
        for tag in tags:
            tag_key = self._build_tag_key(tag)
            await pipe.sadd(tag_key, key)
            await pipe.expire(tag_key, ttl + 60)  # Tag sets live slightly longer

    # Add sync wrapper methods for easier use in sync contexts
    def get_sync(
        self,
        key: str,
        default: Any = None,
        touch: bool = True,
    ) -> Any:
        """
        Sync version of get() with proper async context detection.

        Warns when used in async context and suggests using aget() instead.
        """
        self._warn_sync_in_async("get")

        try:
            # Create the coroutine
            coro = self.get(key, default, touch)
            return asyncio.run(coro)
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                logger.error(
                    "Cannot use sync methods from async context. Use await cache.get() instead."
                )
                if self.config.fallback_enabled:
                    return default
                raise
            raise

    def set_sync(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Union[str, List[str], Set[str]]] = None,
        serialization: Optional[SerializationMethod] = None,
    ) -> bool:
        """Sync version of set()."""
        self._warn_sync_in_async("set")

        try:
            # Create the coroutine
            coro = self.set(key, value, ttl, tags, serialization)
            return asyncio.run(coro)
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                logger.error(
                    "Cannot use sync methods from async context. Use await cache.set() instead."
                )
                if self.config.fallback_enabled:
                    return False
                raise
            raise

    def delete_sync(self, key: str) -> bool:
        """Sync version of delete()."""
        self._warn_sync_in_async("delete")

        try:
            # Create the coroutine
            coro = self.delete(key)
            return asyncio.run(coro)
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                logger.error(
                    "Cannot use sync methods from async context. Use await cache.delete() instead."
                )
                if self.config.fallback_enabled:
                    return False
                raise
            raise

    def exists_sync(self, key: str) -> bool:
        """Sync version of exists()."""
        self._warn_sync_in_async("exists")

        try:
            # Create the coroutine
            coro = self.exists(key)
            return asyncio.run(coro)
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                logger.error(
                    "Cannot use sync methods from async context. Use await cache.exists() instead."
                )
                if self.config.fallback_enabled:
                    return False
                raise
            raise

    # Add aliases for clarity
    async def aget(self, *args, **kwargs) -> Any:
        """Explicitly async version of get."""
        return await self.get(*args, **kwargs)

    async def aset(self, *args, **kwargs) -> bool:
        """Explicitly async version of set."""
        return await self.set(*args, **kwargs)

    async def adelete(self, *args, **kwargs) -> bool:
        """Explicitly async version of delete."""
        return await self.delete(*args, **kwargs)

    async def aexists(self, *args, **kwargs) -> bool:
        """Explicitly async version of exists."""
        return await self.exists(*args, **kwargs)

    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the cache connection."""
        await self.disconnect()

    async def health(self) -> bool:
        """Check if the cache is healthy."""
        try:
            async with self._get_redis() as r:
                await r.ping()
                return True
        except Exception:
            return False

    async def ping(self) -> bool:
        """Ping the cache backend."""
        try:
            async with self._get_redis() as r:
                await r.ping()
                return True
        except Exception:
            return False

    async def flush(self) -> bool:
        """Flush all cache data."""
        try:
            async with self._get_redis() as r:
                await r.flushdb()
                return True
        except Exception as e:
            logger.error(f"Failed to flush cache: {e}")
            return False
