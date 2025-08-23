"""
Redis backend implementation for YokedCache.

This module provides Redis-specific caching functionality with support for
clustering, persistence, and advanced Redis features.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, List, Optional, Set, Union

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from ..exceptions import (
    CacheConnectionError,
    CacheInvalidationError,
    CacheSerializationError,
)
from ..models import CacheEntry, CacheStats, FuzzySearchResult, SerializationMethod
from ..utils import (
    calculate_ttl_with_jitter,
    deserialize_data,
    normalize_tags,
    sanitize_key,
    serialize_data,
)
from .base import CacheBackend

logger = logging.getLogger(__name__)


class RedisBackend(CacheBackend):
    """Redis cache backend implementation."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "yokedcache",
        max_connections: int = 10,
        health_check_interval: int = 30,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
        retry_on_timeout: bool = True,
        default_serialization: SerializationMethod = SerializationMethod.JSON,
        **kwargs,
    ):
        """Initialize Redis backend."""
        super().__init__(**kwargs)

        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.max_connections = max_connections
        self.health_check_interval = health_check_interval
        self.socket_connect_timeout = socket_connect_timeout
        self.socket_timeout = socket_timeout
        self.retry_on_timeout = retry_on_timeout
        self.default_serialization = default_serialization

        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None
        self._stats = CacheStats()
        self._start_time = time.time()

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._connected:
            return

        try:
            # Create connection pool
            self._pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                retry_on_timeout=self.retry_on_timeout,
                health_check_interval=self.health_check_interval,
                socket_connect_timeout=self.socket_connect_timeout,
                socket_timeout=self.socket_timeout,
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
                {"redis_url": self.redis_url, "error": str(e)},
            )

    async def disconnect(self) -> None:
        """Close Redis connection."""
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

    def _build_key(self, key: str) -> str:
        """Build full cache key with prefix."""
        expected_prefix = f"{self.key_prefix}:"
        if key.startswith(expected_prefix):
            return sanitize_key(key)
        return sanitize_key(f"{self.key_prefix}:{key}")

    def _build_tag_key(self, tag: str) -> str:
        """Build tag key for storing key sets."""
        return self._build_key(f"tags:{tag}")

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        sanitized_key = self._build_key(key)

        try:
            async with self._get_redis() as r:
                data = await r.get(sanitized_key)

                if data is None:
                    self._stats.add_miss()
                    return default

                # Try multiple serialization methods
                try:
                    value = deserialize_data(data, SerializationMethod.JSON)
                except CacheSerializationError:
                    try:
                        value = deserialize_data(data, SerializationMethod.PICKLE)
                    except CacheSerializationError:
                        logger.warning(
                            f"Failed to deserialize data for key: {sanitized_key}"
                        )
                        return default

                self._stats.add_hit()

                # Update access time
                try:
                    await r.touch(sanitized_key)
                except Exception:
                    pass  # touch might not be supported

                return value

        except Exception as e:
            logger.error(f"Error getting cache key {sanitized_key}: {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> bool:
        """Set value in cache."""
        sanitized_key = self._build_key(key)
        actual_ttl = calculate_ttl_with_jitter(ttl or 300)

        try:
            serialized_data = serialize_data(value, self.default_serialization)

            async with self._get_redis() as r:
                async with r.pipeline() as pipe:
                    await pipe.setex(sanitized_key, actual_ttl, serialized_data)

                    if tags:
                        normalized_tags = normalize_tags(tags)
                        await self._add_tags_to_key(
                            pipe, sanitized_key, normalized_tags, actual_ttl
                        )

                    await pipe.execute()

            self._stats.total_sets += 1
            return True

        except Exception as e:
            logger.error(f"Error setting cache key {sanitized_key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        sanitized_key = self._build_key(key)

        try:
            async with self._get_redis() as r:
                result = await r.delete(sanitized_key)

                if result > 0:
                    self._stats.total_deletes += 1
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
        """Invalidate all keys matching a pattern."""
        full_pattern = self._build_key(pattern)

        try:
            async with self._get_redis() as r:
                keys = await r.keys(full_pattern)

                if not keys:
                    return 0

                deleted = await r.delete(*keys)
                self._stats.total_invalidations += deleted

                return deleted

        except Exception as e:
            logger.error(f"Error invalidating pattern {pattern}: {e}")
            raise CacheInvalidationError(pattern, "pattern", {"error": str(e)})

    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        """Invalidate all keys associated with given tags."""
        normalized_tags = normalize_tags(tags)
        total_invalidated = 0

        try:
            async with self._get_redis() as r:
                for tag in normalized_tags:
                    tag_key = self._build_tag_key(tag)

                    keys = await r.smembers(tag_key)

                    if keys:
                        deleted = await r.delete(*keys)
                        total_invalidated += deleted

                        await r.delete(tag_key)

                self._stats.total_invalidations += total_invalidated
                return total_invalidated

        except Exception as e:
            logger.error(f"Error invalidating tags {list(normalized_tags)}: {e}")
            raise CacheInvalidationError(
                str(normalized_tags), "tags", {"error": str(e)}
            )

    async def flush_all(self) -> bool:
        """Flush all cache keys with the configured prefix."""
        try:
            async with self._get_redis() as r:
                pattern = self._build_key("*")
                keys = await r.keys(pattern)

                if not keys:
                    deleted = 0
                else:
                    deleted = await r.delete(*keys)
                    self._stats.total_invalidations += deleted

                logger.warning(f"Flushed all cache keys ({deleted} keys deleted)")
                return True

        except Exception as e:
            logger.error(f"Error flushing cache: {e}")
            return False

    async def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        self._stats.uptime_seconds = time.time() - self._start_time

        try:
            async with self._get_redis() as r:
                info = await r.info("memory")
                self._stats.total_memory_bytes = info.get("used_memory", 0)

                # Get total keys count
                info_keyspace = await r.info("keyspace")
                # Extract DB number from redis_url
                db_info = info_keyspace.get("db0", {})  # Default to db0
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
        """Perform fuzzy search on cached data."""
        try:
            from fuzzywuzzy import fuzz, process
        except ImportError:
            logger.error("fuzzywuzzy library not available for fuzzy search")
            return []

        results: List[FuzzySearchResult] = []

        try:
            async with self._get_redis() as r:
                # Get keys to search
                if tags:
                    search_keys_set = set()
                    for tag in tags:
                        tag_key = self._build_tag_key(tag)
                        tag_keys = await r.smembers(tag_key)
                        search_keys_set.update(tag_keys)
                    search_keys = list(search_keys_set)
                else:
                    pattern = self._build_key("*")
                    search_keys = await r.keys(pattern)

                if not search_keys:
                    return results

                # Convert byte keys to strings
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
                            value = await self.get(matched_key)
                            if value is not None:
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

        except Exception as e:
            logger.error(f"Error in fuzzy search: {e}")

        return results

    async def get_all_keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern."""
        full_pattern = self._build_key(pattern)

        try:
            async with self._get_redis() as r:
                keys = await r.keys(full_pattern)
                return [
                    key.decode() if isinstance(key, bytes) else str(key) for key in keys
                ]
        except Exception as e:
            logger.error(f"Error getting keys with pattern {pattern}: {e}")
            return []

    async def get_size_bytes(self) -> int:
        """Get total size of cache in bytes."""
        try:
            async with self._get_redis() as r:
                info = await r.info("memory")
                return info.get("used_memory", 0)
        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return 0

    async def _add_tags_to_key(
        self, pipe: redis.Redis, key: str, tags: Set[str], ttl: int
    ) -> None:
        """Add key to tag sets."""
        for tag in tags:
            tag_key = self._build_tag_key(tag)
            await pipe.sadd(tag_key, key)
            await pipe.expire(tag_key, ttl + 60)  # Tag sets live slightly longer
