"""
YokedCache - A robust, performance-focused caching library for Python backends.

YokedCache provides seamless caching integration for FastAPI applications with Redis,
featuring automatic cache invalidation, fuzzy search capabilities, and intelligent
database integration.
"""

__version__ = "0.1.1"
__author__ = "Project Yoked LLC"
__email__ = "twogoodgamer2@gmail.com"
__license__ = "MIT"

from .cache import YokedCache
from .config import CacheConfig
from .decorators import cached, cached_dependency
from .exceptions import (
    CacheConnectionError,
    CacheKeyError,
    CacheSerializationError,
    YokedCacheError,
)
from .models import CacheEntry, CacheStats, InvalidationRule
from .utils import deserialize_data, generate_cache_key, serialize_data

__all__ = [
    # Core classes
    "YokedCache",
    "CacheConfig",
    # Decorators and utilities
    "cached",
    "cached_dependency",
    # Models
    "CacheEntry",
    "CacheStats",
    "InvalidationRule",
    # Exceptions
    "YokedCacheError",
    "CacheConnectionError",
    "CacheKeyError",
    "CacheSerializationError",
    # Utilities
    "generate_cache_key",
    "serialize_data",
    "deserialize_data",
]
