"""DiskCache backend implementation (optional).

Requires the ``diskcache`` package. Uses ``diskcache.JSONDisk`` and stores
base64-wrapped bytes from ``serialize_for_cache`` so cache values are not
pickle-serialized on disk.
"""

from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Set, Union

try:  # pragma: no cover - optional dependency
    import diskcache
except Exception:  # pragma: no cover - optional dependency missing
    diskcache = None

from ..models import CacheStats, FuzzySearchResult, SerializationMethod
from ..utils import deserialize_from_cache, serialize_for_cache
from .base import CacheBackend

_DISK_VALUE_KEY = "__yc_disk_v1"


class DiskCacheBackend(CacheBackend):  # pragma: no cover - thin wrapper
    """Disk based backend using optional diskcache library (JSONDisk)."""

    def __init__(
        self,
        directory: str = ".yokedcache",
        default_serialization: SerializationMethod = SerializationMethod.JSON,
        allow_legacy_insecure_deserialization: bool = True,
        **config,
    ):
        super().__init__(**config)
        self._directory = directory
        self._cache: Optional[Any] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self.default_serialization = default_serialization
        self.allow_legacy_insecure_deserialization = (
            allow_legacy_insecure_deserialization
        )

    async def _run(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        ex = self._executor
        if ex is None:
            raise RuntimeError("DiskCacheBackend is not connected")
        return await loop.run_in_executor(ex, lambda: func(*args, **kwargs))

    def _wrap_stored(self, blob: bytes) -> dict[str, str]:
        return {_DISK_VALUE_KEY: base64.b64encode(blob).decode("ascii")}

    def _unwrap_stored(self, raw: Any) -> Optional[bytes]:
        if not isinstance(raw, dict):
            return None
        b64 = raw.get(_DISK_VALUE_KEY)
        if not isinstance(b64, str):
            return None
        try:
            return base64.b64decode(b64.encode("ascii"))
        except (ValueError, OSError):
            return None

    async def connect(self) -> None:
        if diskcache is None:
            raise RuntimeError("diskcache is not installed")
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=2)

        def _open() -> Any:
            return diskcache.Cache(self._directory, disk=diskcache.JSONDisk)

        self._cache = await self._run(_open)
        self._connected = True

    async def disconnect(self) -> None:
        if self._cache is not None:
            await self._run(self._cache.close)
            self._cache = None
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None
        self._connected = False

    async def health_check(self) -> bool:
        return self._connected

    async def get(self, key: str, default: Any = None) -> Any:
        if self._cache is None:
            return default
        raw = await self._run(self._cache.get, key, default)
        if raw is default:
            return default
        blob = self._unwrap_stored(raw)
        if blob is None:
            return default
        try:
            return deserialize_from_cache(
                blob, self.allow_legacy_insecure_deserialization
            )
        except Exception:
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> bool:
        if self._cache is None:
            return False
        expire = ttl
        blob = serialize_for_cache(value, self.default_serialization)
        wrapped = self._wrap_stored(blob)
        await self._run(self._cache.set, key, wrapped, expire=expire)
        return True

    async def delete(self, key: str) -> bool:
        if self._cache is None:
            return False
        return await self._run(self._cache.delete, key)

    async def exists(self, key: str) -> bool:
        if self._cache is None:
            return False
        return await self._run(lambda k: k in self._cache, key)

    async def expire(self, key: str, ttl: int) -> bool:
        if self._cache is None:
            return False
        missing = object()
        cur = await self.get(key, missing)
        if cur is missing:
            return False
        return await self.set(key, cur, ttl, None)

    async def invalidate_pattern(self, pattern: str) -> int:
        if self._cache is None:
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
        return 0

    async def flush_all(self) -> bool:
        if self._cache is None:
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
        if self._cache is None:
            return []
        keys: List[str] = []
        prefix = pattern.rstrip("*")
        for k in self._cache.iterkeys():
            if pattern == "*" or str(k).startswith(prefix):
                keys.append(str(k))
        return keys

    async def get_size_bytes(self) -> int:
        if self._cache is None:
            return 0
        return sum(len(str(v)) for v in self._cache.itervalues())
