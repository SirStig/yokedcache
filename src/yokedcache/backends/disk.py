"""DiskCache backend implementation (optional).

Requires the 'diskcache' package. Provides a simple async-compatible wrapper
around diskcache.Cache using a thread executor for blocking operations.

# flake8: noqa
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Set, Union

try:  # pragma: no cover - optional dependency
    import diskcache
except Exception:  # pragma: no cover - optional dependency missing
    diskcache = None

from ..models import CacheStats, FuzzySearchResult
from .base import CacheBackend


class DiskCacheBackend(CacheBackend):  # pragma: no cover - thin wrapper
    """Disk based backend using optional diskcache library."""

    def __init__(self, directory: str = ".yokedcache", **config):
        super().__init__(**config)
        self._directory = directory
        self._cache: Optional[Any] = None
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def _run(self, func, *args, **kwargs):  # small helper
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: func(*args, **kwargs))

    async def connect(self) -> None:
        if diskcache is None:
            raise RuntimeError("diskcache is not installed")
        self._cache = diskcache.Cache(self._directory)
        self._connected = True

    async def disconnect(self) -> None:
        if self._cache:
            await self._run(self._cache.close)
        self._connected = False

    async def health_check(self) -> bool:
        return self._connected

    async def get(self, key: str, default: Any = None) -> Any:
        if not self._cache:
            return default
        return await self._run(self._cache.get, key, default)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> bool:
        if not self._cache:
            return False
        expire = ttl
        await self._run(self._cache.set, key, value, expire=expire)
        return True

    async def delete(self, key: str) -> bool:
        if not self._cache:
            return False
        return await self._run(self._cache.delete, key)

    async def exists(self, key: str) -> bool:
        if not self._cache:
            return False
        return await self._run(lambda k: k in self._cache, key)

    async def expire(self, key: str, ttl: int) -> bool:
        if not self._cache:
            return False
        val = await self._run(self._cache.get, key, None)
        if val is None:
            return False
        await self._run(self._cache.set, key, val, expire=ttl)
        return True

    async def invalidate_pattern(self, pattern: str) -> int:
        if not self._cache:
            return 0
        deleted = 0
        prefix = pattern.rstrip("*")
        for k in list(self._cache.iterkeys()):
            if k.startswith(prefix):
                await self._run(self._cache.delete, k)
                deleted += 1
        return deleted

    async def invalidate_tags(
        self, tags: Union[str, List[str], Set[str]]
    ) -> int:  # noqa: D401,E501
        # Tags not supported in disk backend (no-op)
        return 0

    async def flush_all(self) -> bool:
        if not self._cache:
            return False
        await self._run(self._cache.clear)
        return True

    async def get_stats(self) -> CacheStats:
        return CacheStats()

    async def fuzzy_search(
        self,
        query: str,
        threshold: int = 80,
        max_results: int = 10,
        tags: Optional[Set[str]] = None,
    ) -> List[FuzzySearchResult]:
        return []

    async def get_all_keys(self, pattern: str = "*") -> List[str]:
        if not self._cache:
            return []
        keys: List[str] = []
        prefix = pattern.rstrip("*")
        for k in self._cache.iterkeys():
            if pattern == "*" or str(k).startswith(prefix):
                keys.append(str(k))
        return keys

    async def get_size_bytes(self) -> int:
        if not self._cache:
            return 0
        return sum(len(str(v)) for v in self._cache.itervalues())
