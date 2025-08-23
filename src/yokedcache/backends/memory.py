"""
In-memory backend implementation for YokedCache.

This module provides an in-memory caching backend for development, testing,
and scenarios where persistence is not required.
"""

import asyncio
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Union

from ..models import CacheEntry, CacheStats, FuzzySearchResult, SerializationMethod
from ..utils import calculate_ttl_with_jitter, normalize_tags, sanitize_key
from .base import CacheBackend

logger = logging.getLogger(__name__)


class MemoryBackend(CacheBackend):
    """In-memory cache backend implementation."""

    def __init__(
        self,
        key_prefix: str = "yokedcache",
        max_size: Optional[int] = None,
        cleanup_interval: int = 60,
        **kwargs,
    ):
        """Initialize memory backend."""
        super().__init__(**kwargs)

        self.key_prefix = key_prefix
        self.max_size = max_size  # Maximum number of keys
        self.cleanup_interval = cleanup_interval

        # Storage
        self._storage: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}  # timestamp when key expires
        self._tags: Dict[str, Set[str]] = defaultdict(set)  # tag -> set of keys
        self._key_tags: Dict[str, Set[str]] = defaultdict(set)  # key -> set of tags
        self._access_times: Dict[str, float] = {}

        # Statistics
        self._stats = CacheStats()
        self._start_time = time.time()

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish connection (start cleanup task)."""
        if self._connected:
            return

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_keys())
        self._connected = True
        logger.info("Memory backend connected")

    async def disconnect(self) -> None:
        """Close connection (stop cleanup task)."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self._connected = False
        logger.info("Memory backend disconnected")

    async def health_check(self) -> bool:
        """Check if memory backend is healthy."""
        return self._connected

    def _build_key(self, key: str) -> str:
        """Build full cache key with prefix."""
        expected_prefix = f"{self.key_prefix}:"
        if key.startswith(expected_prefix):
            return sanitize_key(key)
        return sanitize_key(f"{self.key_prefix}:{key}")

    def _is_expired(self, key: str) -> bool:
        """Check if key has expired."""
        if key not in self._expiry:
            return False
        return time.time() > self._expiry[key]

    async def _cleanup_expired_keys(self) -> None:
        """Background task to clean up expired keys."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                async with self._lock:
                    current_time = time.time()
                    expired_keys = [
                        key
                        for key, expiry_time in self._expiry.items()
                        if current_time > expiry_time
                    ]

                    for key in expired_keys:
                        await self._remove_key_internal(key)

                    if expired_keys:
                        logger.debug(f"Cleaned up {len(expired_keys)} expired keys")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

    async def _remove_key_internal(self, key: str) -> None:
        """Remove key and all associated metadata."""
        # Remove from storage
        self._storage.pop(key, None)
        self._expiry.pop(key, None)
        self._access_times.pop(key, None)

        # Remove from tags
        key_tags = self._key_tags.pop(key, set())
        for tag in key_tags:
            self._tags[tag].discard(key)
            if not self._tags[tag]:
                del self._tags[tag]

    async def _evict_if_needed(self) -> None:
        """Evict keys if max_size is exceeded (LRU)."""
        if not self.max_size or len(self._storage) <= self.max_size:
            return

        # Sort by access time and remove oldest
        keys_by_access = sorted(self._access_times.items(), key=lambda x: x[1])

        keys_to_remove = len(self._storage) - self.max_size
        for key, _ in keys_by_access[:keys_to_remove]:
            await self._remove_key_internal(key)
            logger.debug(f"Evicted key due to size limit: {key}")

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        sanitized_key = self._build_key(key)

        async with self._lock:
            if sanitized_key not in self._storage:
                self._stats.add_miss()
                return default

            if self._is_expired(sanitized_key):
                await self._remove_key_internal(sanitized_key)
                self._stats.add_miss()
                return default

            # Update access time
            self._access_times[sanitized_key] = time.time()

            self._stats.add_hit()
            return self._storage[sanitized_key]

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

        async with self._lock:
            try:
                # Remove existing key if present
                if sanitized_key in self._storage:
                    await self._remove_key_internal(sanitized_key)

                # Store value
                self._storage[sanitized_key] = value
                self._expiry[sanitized_key] = time.time() + actual_ttl
                self._access_times[sanitized_key] = time.time()

                # Handle tags
                if tags:
                    normalized_tags = normalize_tags(tags)
                    self._key_tags[sanitized_key] = normalized_tags
                    for tag in normalized_tags:
                        self._tags[tag].add(sanitized_key)

                # Evict if needed
                await self._evict_if_needed()

                self._stats.total_sets += 1
                return True

            except Exception as e:
                logger.error(f"Error setting cache key {sanitized_key}: {e}")
                return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        sanitized_key = self._build_key(key)

        async with self._lock:
            if sanitized_key in self._storage:
                await self._remove_key_internal(sanitized_key)
                self._stats.total_deletes += 1
                return True

            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        sanitized_key = self._build_key(key)

        async with self._lock:
            if sanitized_key not in self._storage:
                return False

            if self._is_expired(sanitized_key):
                await self._remove_key_internal(sanitized_key)
                return False

            return True

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for existing key."""
        sanitized_key = self._build_key(key)

        async with self._lock:
            if sanitized_key in self._storage and not self._is_expired(sanitized_key):
                self._expiry[sanitized_key] = time.time() + ttl
                return True

            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        import fnmatch

        full_pattern = self._build_key(pattern)

        async with self._lock:
            matching_keys = [
                key
                for key in self._storage.keys()
                if fnmatch.fnmatch(key, full_pattern)
            ]

            for key in matching_keys:
                await self._remove_key_internal(key)

            invalidated = len(matching_keys)
            self._stats.total_invalidations += invalidated

            return invalidated

    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        """Invalidate all keys associated with given tags."""
        normalized_tags = normalize_tags(tags)
        total_invalidated = 0

        async with self._lock:
            keys_to_remove = set()

            for tag in normalized_tags:
                if tag in self._tags:
                    keys_to_remove.update(self._tags[tag])

            for key in keys_to_remove:
                await self._remove_key_internal(key)
                total_invalidated += 1

            self._stats.total_invalidations += total_invalidated
            return total_invalidated

    async def flush_all(self) -> bool:
        """Flush all cache keys with the configured prefix."""
        async with self._lock:
            prefix = f"{self.key_prefix}:"
            keys_to_remove = [
                key for key in self._storage.keys() if key.startswith(prefix)
            ]

            for key in keys_to_remove:
                await self._remove_key_internal(key)

            deleted = len(keys_to_remove)
            self._stats.total_invalidations += deleted

            logger.warning(f"Flushed all cache keys ({deleted} keys deleted)")
            return True

    async def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        async with self._lock:
            # Ensure uptime is at least a small value to avoid 0.0 in fast tests
            uptime = time.time() - self._start_time
            self._stats.uptime_seconds = max(uptime, 0.001)  # Minimum 1ms uptime
            self._stats.total_keys = len(self._storage)

            # Calculate approximate memory usage
            total_size = 0
            for key, value in self._storage.items():
                total_size += sys.getsizeof(key) + sys.getsizeof(value)

            self._stats.total_memory_bytes = total_size

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

        async with self._lock:
            # Get keys to search
            if tags:
                search_keys_set = set()
                for tag in tags:
                    if tag in self._tags:
                        search_keys_set.update(self._tags[tag])
                search_keys = list(search_keys_set)
            else:
                prefix = f"{self.key_prefix}:"
                search_keys = [
                    key for key in self._storage.keys() if key.startswith(prefix)
                ]

            if not search_keys:
                return results

            # Perform fuzzy matching
            matches = process.extract(
                query, search_keys, scorer=fuzz.partial_ratio, limit=max_results
            )

            # Get values for matching keys
            for match in matches:
                matched_key, score = match[:2]  # Take first two elements
                if score >= threshold:
                    try:
                        if matched_key in self._storage and not self._is_expired(
                            matched_key
                        ):
                            value = self._storage[matched_key]
                            result = FuzzySearchResult(
                                key=matched_key,
                                value=value,
                                score=score,
                                matched_term=query,
                                cache_entry=CacheEntry(
                                    key=matched_key,
                                    value=value,
                                    created_at=datetime.now(timezone.utc),
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
        import fnmatch

        full_pattern = self._build_key(pattern)

        async with self._lock:
            return [
                key
                for key in self._storage.keys()
                if fnmatch.fnmatch(key, full_pattern) and not self._is_expired(key)
            ]

    async def get_size_bytes(self) -> int:
        """Get total size of cache in bytes."""
        async with self._lock:
            total_size = 0
            for key, value in self._storage.items():
                total_size += sys.getsizeof(key) + sys.getsizeof(value)
            return total_size
