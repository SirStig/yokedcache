"""
YokedCache backend interfaces and implementations.

This module provides backend abstractions for different caching mechanisms,
including Redis, Memcached, and in-memory storage.
"""

from .base import CacheBackend
from .memory import MemoryBackend
from .redis import RedisBackend

try:
    from .memcached import MemcachedBackend

    MEMCACHED_AVAILABLE = True
except ImportError:
    MEMCACHED_AVAILABLE = False
    MemcachedBackend = None  # type: ignore

__all__ = [
    "CacheBackend",
    "RedisBackend",
    "MemoryBackend",
    "MemcachedBackend",
    "MEMCACHED_AVAILABLE",
]
