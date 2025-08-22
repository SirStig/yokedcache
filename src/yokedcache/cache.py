"""
Core YokedCache implementation.

This module contains the main YokedCache class that provides the primary
caching functionality, including Redis integration, auto-invalidation,
and cache management operations.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Union

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from .config import CacheConfig
from .exceptions import (
    CacheConnectionError,
    CacheInvalidationError,
    CacheKeyError,
    CacheSerializationError,
    CacheTimeoutError,
    YokedCacheError,
)
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
    ) -> None:
        """
        Initialize YokedCache.

        Args:
            config: CacheConfig instance
            redis_url: Redis connection URL (overrides config)
            config_file: Path to configuration file
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

        # Initialize Redis connection
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None

        # Cache statistics
        self._stats = CacheStats()
        self._start_time = time.time()

        # Internal state
        self._connected = False
        self._shutdown = False

        # Setup logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging based on configuration."""
        logger.setLevel(getattr(logging, self.config.log_level.upper(), logging.INFO))

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._connected:
            return

        try:
            # Create connection pool
            self._pool = ConnectionPool.from_url(
                self.config.redis_url,
                max_connections=self.config.max_connections,
                retry_on_timeout=self.config.retry_on_timeout,
                health_check_interval=self.config.health_check_interval,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_timeout=self.config.socket_timeout,
            )

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

    @asynccontextmanager
    async def _get_redis(self) -> AsyncGenerator[redis.Redis, None]:
        """Get Redis client with automatic connection management."""
        if not self._connected:
            await self.connect()

        if not self._redis:
            raise CacheConnectionError("Redis client not available")

        yield self._redis

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

        try:
            async with self._get_redis() as r:
                # Get value from Redis
                data = await r.get(sanitized_key)

                if data is None:
                    self._stats.add_miss()
                    if self.config.log_cache_misses:
                        logger.debug(f"Cache miss: {sanitized_key}")
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

                # Update access time if requested
                if touch:
                    await r.touch(sanitized_key)

                if self.config.log_cache_hits:
                    logger.debug(f"Cache hit: {sanitized_key}")

                return value

        except Exception as e:
            logger.error(f"Error getting cache key {sanitized_key}: {e}")
            return default

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

        try:
            # Serialize value
            serialized_data = serialize_data(value, serialization)

            async with self._get_redis() as r:
                # Start pipeline for atomic operations
                async with r.pipeline() as pipe:
                    # Set the main key
                    await pipe.setex(sanitized_key, actual_ttl, serialized_data)

                    # Handle tags
                    if tags:
                        normalized_tags = normalize_tags(tags)
                        await self._add_tags_to_key(
                            pipe, sanitized_key, normalized_tags, actual_ttl
                        )

                    # Execute pipeline
                    await pipe.execute()

            self._stats.total_sets += 1
            logger.debug(f"Cache set: {sanitized_key} (TTL: {actual_ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error setting cache key {sanitized_key}: {e}")
            return False

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
        pattern = self._build_key("*")

        try:
            deleted = await self.invalidate_pattern("*")
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
                for matched_key, score in matches:
                    if score >= threshold:
                        try:
                            value = await self.get(matched_key, touch=False)
                            if value is not None:
                                from .models import CacheEntry

                                result = FuzzySearchResult(
                                    key=matched_key,
                                    value=value,
                                    score=score,
                                    matched_term=query,
                                    cache_entry=CacheEntry(
                                        key=matched_key,
                                        value=value,
                                        created_at=datetime.utcnow(),
                                    ),
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
        if key.startswith(self.config.key_prefix):
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

    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
