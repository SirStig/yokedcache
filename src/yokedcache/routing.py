"""
Prefix-based routing and sharding for YokedCache.

Enables routing cache operations to different backends based on key prefixes,
allowing for horizontal scaling and backend specialization.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Union

from .backends.base import CacheBackend
from .models import CacheStats, FuzzySearchResult

logger = logging.getLogger(__name__)


class PrefixRouter:
    """Routes cache operations to backends based on key prefixes."""

    def __init__(self, default_backend: CacheBackend):
        """Initialize with a default backend for unmatched prefixes."""
        self.default_backend = default_backend
        self.prefix_map: Dict[str, CacheBackend] = {}
        self._connected_backends: Set[CacheBackend] = set()

    def add_route(self, prefix: str, backend: CacheBackend) -> None:
        """Add a prefix -> backend mapping."""
        self.prefix_map[prefix] = backend
        logger.debug(f"Added route: {prefix} -> {type(backend).__name__}")

    def remove_route(self, prefix: str) -> bool:
        """Remove a prefix route. Returns True if removed."""
        if prefix in self.prefix_map:
            del self.prefix_map[prefix]
            logger.debug(f"Removed route: {prefix}")
            return True
        return False

    def get_backend(self, key: str) -> CacheBackend:
        """Get the appropriate backend for a given key."""
        # Find the longest matching prefix
        best_match = ""
        for prefix in self.prefix_map:
            if key.startswith(prefix) and len(prefix) > len(best_match):
                best_match = prefix

        if best_match:
            return self.prefix_map[best_match]
        return self.default_backend

    async def connect_all(self) -> None:
        """Connect all registered backends."""
        all_backends = {self.default_backend} | set(self.prefix_map.values())

        for backend in all_backends:
            if backend not in self._connected_backends:
                try:
                    await backend.connect()
                    self._connected_backends.add(backend)
                    logger.debug(f"Connected backend: {type(backend).__name__}")
                except Exception as e:
                    logger.error(
                        f"Failed to connect backend {type(backend).__name__}: {e}"
                    )

    async def disconnect_all(self) -> None:
        """Disconnect all backends."""
        for backend in self._connected_backends:
            try:
                await backend.disconnect()
                logger.debug(f"Disconnected backend: {type(backend).__name__}")
            except Exception as e:
                logger.error(
                    f"Error disconnecting backend {type(backend).__name__}: {e}"
                )

        self._connected_backends.clear()

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all backends."""
        results = {}

        # Check default backend
        try:
            results["default"] = await self.default_backend.health_check()
        except Exception:
            results["default"] = False

        # Check prefix backends
        for prefix, backend in self.prefix_map.items():
            try:
                results[f"prefix:{prefix}"] = await backend.health_check()
            except Exception:
                results[f"prefix:{prefix}"] = False

        return results

    # Routing methods that delegate to appropriate backend

    async def get(self, key: str, default: Any = None) -> Any:
        """Route get operation to appropriate backend."""
        backend = self.get_backend(key)
        return await backend.get(key, default)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> bool:
        """Route set operation to appropriate backend."""
        backend = self.get_backend(key)
        return await backend.set(key, value, ttl, tags)

    async def delete(self, key: str) -> bool:
        """Route delete operation to appropriate backend."""
        backend = self.get_backend(key)
        return await backend.delete(key)

    async def exists(self, key: str) -> bool:
        """Route exists operation to appropriate backend."""
        backend = self.get_backend(key)
        return await backend.exists(key)

    async def expire(self, key: str, ttl: int) -> bool:
        """Route expire operation to appropriate backend."""
        backend = self.get_backend(key)
        return await backend.expire(key, ttl)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate pattern across all relevant backends."""
        total_invalidated = 0

        # Check which backends might have matching keys
        backends_to_check = {self.default_backend}

        # If pattern starts with a known prefix, only check that backend
        for prefix in self.prefix_map:
            if pattern.startswith(prefix):
                backends_to_check = {self.prefix_map[prefix]}
                break
        else:
            # Pattern doesn't match a specific prefix, check all backends
            backends_to_check.update(self.prefix_map.values())

        for backend in backends_to_check:
            try:
                count = await backend.invalidate_pattern(pattern)
                total_invalidated += count
            except Exception as e:
                logger.error(
                    f"Error invalidating pattern {pattern} on {type(backend).__name__}: {e}"
                )

        return total_invalidated

    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        """Invalidate tags across all backends."""
        total_invalidated = 0
        all_backends = {self.default_backend} | set(self.prefix_map.values())

        for backend in all_backends:
            try:
                count = await backend.invalidate_tags(tags)
                total_invalidated += count
            except Exception as e:
                logger.error(
                    f"Error invalidating tags on {type(backend).__name__}: {e}"
                )

        return total_invalidated

    async def flush_all(self) -> bool:
        """Flush all backends."""
        success = True
        all_backends = {self.default_backend} | set(self.prefix_map.values())

        for backend in all_backends:
            try:
                result = await backend.flush_all()
                success = success and result
            except Exception as e:
                logger.error(f"Error flushing {type(backend).__name__}: {e}")
                success = False

        return success

    async def get_stats(self) -> Dict[str, CacheStats]:
        """Get stats from all backends."""
        stats = {}

        # Default backend stats
        try:
            stats["default"] = await self.default_backend.get_stats()
        except Exception as e:
            logger.error(f"Error getting stats from default backend: {e}")
            stats["default"] = CacheStats()

        # Prefix backend stats
        for prefix, backend in self.prefix_map.items():
            try:
                stats[f"prefix:{prefix}"] = await backend.get_stats()
            except Exception as e:
                logger.error(f"Error getting stats from {prefix} backend: {e}")
                stats[f"prefix:{prefix}"] = CacheStats()

        return stats

    async def fuzzy_search(
        self,
        query: str,
        threshold: int = 80,
        max_results: int = 10,
        tags: Optional[Set[str]] = None,
    ) -> List[FuzzySearchResult]:
        """Perform fuzzy search across all backends."""
        all_results = []
        all_backends = {self.default_backend} | set(self.prefix_map.values())

        for backend in all_backends:
            try:
                results = await backend.fuzzy_search(
                    query, threshold, max_results, tags
                )
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error in fuzzy search on {type(backend).__name__}: {e}")

        # Sort by score and limit results
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:max_results]

    async def get_all_keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern from all backends."""
        all_keys = []
        all_backends = {self.default_backend} | set(self.prefix_map.values())

        for backend in all_backends:
            try:
                keys = await backend.get_all_keys(pattern)
                all_keys.extend(keys)
            except Exception as e:
                logger.error(f"Error getting keys from {type(backend).__name__}: {e}")

        return list(set(all_keys))  # Remove duplicates

    async def get_size_bytes(self) -> int:
        """Get total size across all backends."""
        total_size = 0
        all_backends = {self.default_backend} | set(self.prefix_map.values())

        for backend in all_backends:
            try:
                size = await backend.get_size_bytes()
                total_size += size
            except Exception as e:
                logger.error(f"Error getting size from {type(backend).__name__}: {e}")

        return total_size
