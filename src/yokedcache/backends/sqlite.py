"""SQLite backend (async) using aiosqlite (optional).

Simplified key-value store with TTL column and tag-based invalidation.
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

from ..models import CacheStats, FuzzySearchResult, SerializationMethod
from ..utils import deserialize_from_cache, normalize_tags, serialize_for_cache
from .base import CacheBackend


class SQLiteBackend(CacheBackend):  # pragma: no cover - thin wrapper
    def __init__(
        self,
        path: str = ":memory:",
        default_serialization: SerializationMethod = SerializationMethod.JSON,
        allow_legacy_insecure_deserialization: bool = False,
        **config,
    ):
        super().__init__(**config)
        self._path = path
        self._db: Optional[Any] = None
        self._lock = asyncio.Lock()
        self.default_serialization = default_serialization
        self.allow_legacy_insecure_deserialization = (
            allow_legacy_insecure_deserialization
        )

    async def connect(self) -> None:
        if self._connected:
            return
        if aiosqlite is None:
            raise RuntimeError("aiosqlite not installed")
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS yokedcache (
                k TEXT PRIMARY KEY,
                v BLOB,
                expire_at REAL
            )
            """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS yokedcache_tags (
                tag TEXT NOT NULL,
                k TEXT NOT NULL,
                PRIMARY KEY (tag, k)
            )
            """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS yokedcache_tags_k ON yokedcache_tags (k)"
        )
        await self._db.commit()
        self._connected = True

    async def disconnect(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
        self._connected = False

    async def health_check(self) -> bool:
        return self._connected

    async def _delete_locked(self, key: str) -> bool:
        """Delete a key and its tag rows. Caller must already hold ``self._lock``."""
        assert self._db is not None  # callers only reach here after their own guard
        cur = await self._db.execute("DELETE FROM yokedcache WHERE k=?", (key,))
        await self._db.execute("DELETE FROM yokedcache_tags WHERE k=?", (key,))
        await self._db.commit()
        return cur.rowcount > 0

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
                # Delete inline while still holding the lock instead of
                # calling the public delete() (which also acquires it) -
                # asyncio.Lock isn't reentrant, so doing that deadlocks
                # every subsequent call on this backend.
                await self._delete_locked(key)
                return default

            try:
                return deserialize_from_cache(
                    bytes(value), self.allow_legacy_insecure_deserialization
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
        if not self._db:
            return False
        actual_ttl = ttl or 300
        expire_at = time.time() + actual_ttl
        blob = serialize_for_cache(value, self.default_serialization)

        async with self._lock:
            await self._db.execute(
                "REPLACE INTO yokedcache (k, v, expire_at) VALUES (?, ?, ?)",
                (key, blob, expire_at),
            )
            await self._db.execute("DELETE FROM yokedcache_tags WHERE k=?", (key,))
            if tags:
                normalized_tags = normalize_tags(tags)
                await self._db.executemany(
                    "INSERT OR IGNORE INTO yokedcache_tags (tag, k) VALUES (?, ?)",
                    [(tag, key) for tag in normalized_tags],
                )
            await self._db.commit()
        return True

    async def delete(self, key: str) -> bool:
        if not self._db:
            return False
        async with self._lock:
            return await self._delete_locked(key)

    async def exists(self, key: str) -> bool:
        if not self._db:
            return False
        async with self._lock:
            async with self._db.execute(
                "SELECT expire_at FROM yokedcache WHERE k=?", (key,)
            ) as cur:
                row = await cur.fetchone()

            if not row:
                return False

            expire_at = row[0]
            if expire_at and expire_at < time.time():
                await self._delete_locked(key)
                return False

            return True

    async def expire(self, key: str, ttl: int) -> bool:
        if not self._db:
            return False
        expire_at = time.time() + ttl
        async with self._lock:
            cur = await self._db.execute(
                "UPDATE yokedcache SET expire_at=? WHERE k=?", (expire_at, key)
            )
            await self._db.commit()
            return cur.rowcount > 0

    async def invalidate_pattern(self, pattern: str) -> int:
        if not self._db:
            return 0
        like_pattern = pattern.replace("*", "%")
        async with self._lock:
            async with self._db.execute(
                "SELECT k FROM yokedcache WHERE k LIKE ?", (like_pattern,)
            ) as cur:
                keys = [r[0] for r in await cur.fetchall()]

            cur = await self._db.execute(
                "DELETE FROM yokedcache WHERE k LIKE ?", (like_pattern,)
            )
            if keys:
                await self._db.executemany(
                    "DELETE FROM yokedcache_tags WHERE k=?", [(k,) for k in keys]
                )
            await self._db.commit()
            return cur.rowcount or 0

    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        if not self._db:
            return 0
        normalized_tags = normalize_tags(tags)
        if not normalized_tags:
            return 0

        placeholders = ",".join("?" for _ in normalized_tags)
        async with self._lock:
            async with self._db.execute(
                f"SELECT DISTINCT k FROM yokedcache_tags WHERE tag IN ({placeholders})",
                tuple(normalized_tags),
            ) as cur:
                keys = [r[0] for r in await cur.fetchall()]

            for key in keys:
                await self._db.execute("DELETE FROM yokedcache WHERE k=?", (key,))
                await self._db.execute("DELETE FROM yokedcache_tags WHERE k=?", (key,))
            await self._db.commit()
            return len(keys)

    async def flush_all(self) -> bool:
        if not self._db:
            return False
        async with self._lock:
            await self._db.execute("DELETE FROM yokedcache")
            await self._db.execute("DELETE FROM yokedcache_tags")
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
                "SELECT k FROM yokedcache WHERE k LIKE ? "
                "AND (expire_at IS NULL OR expire_at >= ?)",
                (like_pattern, time.time()),
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
                return sum(len(r[0]) if r[0] is not None else 0 for r in rows)
