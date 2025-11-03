"""
Memcached backend implementation for YokedCache.

This module provides Memcached-specific caching functionality with support for
distributed caching across multiple Memcached servers.
"""

import logging
import time
from datetime import datetime
from typing import Any, List, Optional, Set, Union

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

try:
    import aiomcache

    AIOMCACHE_AVAILABLE = True
except ImportError:
    AIOMCACHE_AVAILABLE = False
    aiomcache = None


class MemcachedBackend(CacheBackend):
    """Memcached cache backend implementation."""

    def __init__(
        self,
        servers: Optional[List[str]] = None,
        key_prefix: str = "yokedcache",
        default_serialization: SerializationMethod = SerializationMethod.PICKLE,
        pool_size: int = 2,
        pool_minsize: int = 1,
        **kwargs,
    ):
        """Initialize Memcached backend."""
        if not AIOMCACHE_AVAILABLE:
            raise ImportError(
                "aiomcache is required for Memcached backend. "
                "Install with: pip install aiomcache"
            )

        super().__init__(**kwargs)

        self.servers = servers or ["localhost:11211"]
        self.key_prefix = key_prefix
        self.default_serialization = default_serialization
        self.pool_size = pool_size
        self.pool_minsize = pool_minsize

        # Convert string servers to tuples if needed
        self.server_tuples = []
        for server in self.servers:
            if isinstance(server, str):
                if ":" in server:
                    host, port_str = server.split(":")
                    self.server_tuples.append((host, int(port_str)))
                else:
                    self.server_tuples.append((server, 11211))
            else:
                self.server_tuples.append(server)

        self._client: Optional[aiomcache.Client] = None
        self._stats = CacheStats()
        self._start_time = time.time()

        # Tag storage - Memcached doesn't support sets, so we'll simulate them
        self._tag_storage: dict = {}  # This would need external storage in production

    async def connect(self) -> None:
        """Establish connection to Memcached."""
        if self._connected:
            return

        try:
            self._client = aiomcache.Client(
                *self.server_tuples[
                    0
                ],  # aiomcache only supports single server per client
                pool_size=self.pool_size,
                pool_minsize=self.pool_minsize,
            )

            # Test connection
            await self._client.version()

            self._connected = True
            logger.info(f"Connected to Memcached at {self.server_tuples[0]}")

        except Exception as e:
            self._connected = False
            raise Exception(f"Failed to connect to Memcached: {e}")

    async def disconnect(self) -> None:
        """Close Memcached connection."""
        if self._client:
            await self._client.close()

        self._connected = False
        logger.info("Disconnected from Memcached")

    async def health_check(self) -> bool:
        """Check if Memcached connection is healthy."""
        if not self._connected or not self._client:
            return False

        try:
            await self._client.version()
            return True
        except Exception as e:
            logger.warning(f"Memcached health check failed: {e}")
            return False

    def _build_key(self, key: str) -> str:
        """Build cache key with prefix."""
        expected_prefix = f"{self.key_prefix}:"
        if key.startswith(expected_prefix):
            return sanitize_key(key)
        return sanitize_key(f"{self.key_prefix}:{key}")

    def _build_tag_key(self, tag: str) -> str:
        """Build tag key for storing key sets."""
        return self._build_key(f"tags:{tag}")

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        if not self._client:
            return default

        sanitized_key = self._build_key(key)

        try:
            data = await self._client.get(sanitized_key.encode())

            if data is None:
                self._stats.add_miss()
                return default

            # Deserialize data
            try:
                value = deserialize_data(data, self.default_serialization)
            except Exception:
                try:
                    # Fallback to JSON
                    value = deserialize_data(data, SerializationMethod.JSON)
                except Exception:
                    logger.warning(
                        f"Failed to deserialize data for key: {sanitized_key}"
                    )
                    return default

            self._stats.add_hit()
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
        if not self._client:
            return False

        sanitized_key = self._build_key(key)
        actual_ttl = calculate_ttl_with_jitter(ttl or 300)

        try:
            serialized_data = serialize_data(value, self.default_serialization)

            success = await self._client.set(
                sanitized_key.encode(), serialized_data, exptime=actual_ttl
            )

            if success and tags:
                # Handle tags (simplified - in production you'd want persistent tag storage)
                normalized_tags = normalize_tags(tags)
                for tag in normalized_tags:
                    if tag not in self._tag_storage:
                        self._tag_storage[tag] = set()
                    self._tag_storage[tag].add(sanitized_key)

            if success:
                self._stats.total_sets += 1

            return success

        except Exception as e:
            logger.error(f"Error setting cache key {sanitized_key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._client:
            return False

        sanitized_key = self._build_key(key)

        try:
            success = await self._client.delete(sanitized_key.encode())

            if success:
                self._stats.total_deletes += 1

                # Remove from tags
                for tag, keys in self._tag_storage.items():
                    keys.discard(sanitized_key)

            return success

        except Exception as e:
            logger.error(f"Error deleting cache key {sanitized_key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        value = await self.get(key, None)
        return value is not None

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for existing key."""
        # Memcached doesn't have a direct expire command
        # We need to get the value and set it again with new TTL
        value = await self.get(key, None)
        if value is not None:
            return await self.set(key, value, ttl=ttl)
        return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        # Memcached doesn't support pattern-based operations
        # This would require maintaining a separate index of keys
        logger.warning("Pattern invalidation not fully supported in Memcached backend")
        return 0

    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        """Invalidate all keys associated with given tags."""
        normalized_tags = normalize_tags(tags)
        total_invalidated = 0

        try:
            for tag in normalized_tags:
                if tag in self._tag_storage:
                    keys_to_delete = list(self._tag_storage[tag])

                    for key in keys_to_delete:
                        if await self.delete(key):
                            total_invalidated += 1

                    # Clear the tag
                    del self._tag_storage[tag]

            self._stats.total_invalidations += total_invalidated
            return total_invalidated

        except Exception as e:
            logger.error(f"Error invalidating tags {list(normalized_tags)}: {e}")
            return 0

    async def flush_all(self) -> bool:
        """Flush all cache keys."""
        if not self._client:
            return False

        try:
            await self._client.flush_all()
            self._tag_storage.clear()
            logger.warning("Flushed all Memcached keys")
            return True

        except Exception as e:
            logger.error(f"Error flushing cache: {e}")
            return False

    async def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        self._stats.uptime_seconds = time.time() - self._start_time

        try:
            if self._client:
                stats = await self._client.stats()
                # Parse Memcached stats
                if stats:
                    stats_dict = dict(stats)
                    bytes_val = stats_dict.get(b"bytes", b"0")
                    items_val = stats_dict.get(b"curr_items", b"0")
                    self._stats.total_memory_bytes = (
                        int(bytes_val) if bytes_val is not None else 0
                    )
                    self._stats.total_keys = (
                        int(items_val) if items_val is not None else 0
                    )

        except Exception as e:
            logger.debug(f"Could not get Memcached stats: {e}")

        return self._stats

    async def fuzzy_search(
        self,
        query: str,
        threshold: int = 80,
        max_results: int = 10,
        tags: Optional[Set[str]] = None,
    ) -> List[FuzzySearchResult]:
        """Perform fuzzy search on cached data."""
        # Memcached doesn't support key iteration, so fuzzy search is limited
        logger.warning("Fuzzy search has limited functionality in Memcached backend")

        try:
            from fuzzywuzzy import fuzz, process
        except ImportError:
            logger.error("fuzzywuzzy library not available for fuzzy search")
            return []

        results: List[FuzzySearchResult] = []

        # Can only search within tagged keys if tags are provided
        if tags:
            search_keys_set = set()
            for tag in tags:
                if tag in self._tag_storage:
                    search_keys_set.update(self._tag_storage[tag])

            search_keys = list(search_keys_set)

            if search_keys:
                matches = process.extract(
                    query, search_keys, scorer=fuzz.partial_ratio, limit=max_results
                )

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

        return results

    async def get_all_keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern."""
        # Memcached doesn't support key enumeration
        logger.warning("Key enumeration not supported in Memcached backend")
        return []

    async def get_size_bytes(self) -> int:
        """Get total size of cache in bytes."""
        try:
            if self._client:
                stats = await self._client.stats()
                if stats:
                    stats_dict = dict(stats)
                    bytes_val = stats_dict.get(b"bytes", b"0")
                    return int(bytes_val) if bytes_val is not None else 0
        except Exception as e:
            logger.error(f"Error getting cache size: {e}")

        return 0
