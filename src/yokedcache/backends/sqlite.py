"""SQLite backend (async) using aiosqlite (optional).

Simplified key-value store with TTL column.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, List, Optional, Set, Union

if TYPE_CHECKING:
    import aiosqlite
else:
    try:  # pragma: no cover - optional dependency
        import aiosqlite  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        aiosqlite = None  # type: ignore[assignment]

from ..models import CacheStats, FuzzySearchResult
from .base import CacheBackend


class SQLiteBackend(CacheBackend):  # pragma: no cover - thin wrapper
    def __init__(self, path: str = ":memory:", **config):
        super().__init__(**config)
        self._path = path
        self._db: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if aiosqlite is None:
            raise RuntimeError("aiosqlite not installed")
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS yokedcache (
                k TEXT PRIMARY KEY,
                v BLOB,
                expire_at REAL
            )
            """
        )
        await self._db.commit()
        self._connected = True

    async def disconnect(self) -> None:
        if self._db:
            await self._db.close()
        self._connected = False

    async def health_check(self) -> bool:
        return self._connected

    async def get(self, key: str, default: Any = None) -> Any:
        if not self._db:
            return default
        async with self._lock:
            async with self._db.execute(
                "SELECT v, expire_at FROM yokedcache WHERE k=?", (key,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return default
                value, expire_at = row
                if expire_at and expire_at < time.time():
                    await self.delete(key)
                    return default
                return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> bool:
        if not self._db:
            return False
        expire_at = time.time() + ttl if ttl else None
        async with self._lock:
            await self._db.execute(
                "REPLACE INTO yokedcache (k, v, expire_at) VALUES (?, ?, ?)",
                (key, value, expire_at),
            )
            await self._db.commit()
        return True

    async def delete(self, key: str) -> bool:
        if not self._db:
            return False
        async with self._lock:
            cur = await self._db.execute("DELETE FROM yokedcache WHERE k=?", (key,))
            await self._db.commit()
            return cur.rowcount > 0

    async def exists(self, key: str) -> bool:
        if not self._db:
            return False
        async with self._lock:
            async with self._db.execute(
                "SELECT 1 FROM yokedcache WHERE k=?", (key,)
            ) as cur:
                return await cur.fetchone() is not None

    async def expire(self, key: str, ttl: int) -> bool:
        if not self._db:
            return False
        expire_at = time.time() + ttl
        async with self._lock:
            await self._db.execute(
                "UPDATE yokedcache SET expire_at=? WHERE k=?", (expire_at, key)
            )
            await self._db.commit()
        return True

    async def invalidate_pattern(self, pattern: str) -> int:
        if not self._db:
            return 0
        like_pattern = pattern.replace("*", "%")
        async with self._lock:
            cur = await self._db.execute(
                "DELETE FROM yokedcache WHERE k LIKE ?", (like_pattern,)
            )
            await self._db.commit()
            return cur.rowcount or 0

    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        return 0

    async def flush_all(self) -> bool:
        if not self._db:
            return False
        async with self._lock:
            await self._db.execute("DELETE FROM yokedcache")
            await self._db.commit()
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
        if not self._db:
            return []
        like_pattern = pattern.replace("*", "%")
        async with self._lock:
            async with self._db.execute(
                "SELECT k FROM yokedcache WHERE k LIKE ?", (like_pattern,)
            ) as cur:
                rows = await cur.fetchall()
                return [r[0] for r in rows]

    async def get_size_bytes(self) -> int:
        # naive estimate
        if not self._db:
            return 0
        async with self._lock:
            async with self._db.execute("SELECT v FROM yokedcache") as cur:
                rows = await cur.fetchall()
                return sum(len(str(r[0])) for r in rows)
