"""
YokedCache backend interfaces and implementations.

This module provides backend abstractions for different caching mechanisms,
including Redis, Memcached, and in-memory storage.
"""

from .base import CacheBackend
from .memory import MemoryBackend

try:
    from .redis import RedisBackend

    REDIS_BACKEND_AVAILABLE = True
except ImportError:
    RedisBackend = None  # type: ignore[misc,assignment]
    REDIS_BACKEND_AVAILABLE = False

# Optional disk backend
try:  # pragma: no cover
    from .disk import DiskCacheBackend

    DISK_AVAILABLE = True
except Exception:  # pragma: no cover
    DiskCacheBackend = None  # type: ignore
    DISK_AVAILABLE = False

# Optional sqlite backend
try:  # pragma: no cover
    from .sqlite import SQLiteBackend

    SQLITE_AVAILABLE = True
except Exception:  # pragma: no cover
    SQLiteBackend = None  # type: ignore
    SQLITE_AVAILABLE = False

try:
    from .memcached import MemcachedBackend

    MEMCACHED_AVAILABLE = True
except ImportError:
    MEMCACHED_AVAILABLE = False
    MemcachedBackend = None  # type: ignore

__all__ = [
    "CacheBackend",
    "RedisBackend",
    "REDIS_BACKEND_AVAILABLE",
    "MemoryBackend",
    "MemcachedBackend",
    "MEMCACHED_AVAILABLE",
    "DiskCacheBackend",
    "DISK_AVAILABLE",
    "SQLiteBackend",
    "SQLITE_AVAILABLE",
]
