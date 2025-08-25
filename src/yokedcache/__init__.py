"""
YokedCache - A robust, performance-focused caching library for Python backends.

YokedCache provides seamless caching integration for FastAPI applications with Redis,
featuring automatic cache invalidation, fuzzy search capabilities, and intelligent
database integration.
"""

__version__ = "0.2.3"
__author__ = "Project Yoked LLC"
__email__ = "twogoodgamer2@gmail.com"
__license__ = "MIT"

try:
    from .cache import YokedCache
except ImportError:
    # If Redis is not available, create a placeholder that gives helpful error
    class YokedCache:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Redis is required for YokedCache. Please install with: "
                "pip install redis>=4.0.0"
            )


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

# Import backends with optional dependencies
try:
    from .backends import MEMCACHED_AVAILABLE, CacheBackend, MemoryBackend, RedisBackend

    if MEMCACHED_AVAILABLE:
        from .backends import MemcachedBackend
    else:
        MemcachedBackend = None  # type: ignore
except ImportError:
    # Backends not available
    CacheBackend = None  # type: ignore
    RedisBackend = None  # type: ignore
    MemoryBackend = None  # type: ignore
    MemcachedBackend = None  # type: ignore

# Import monitoring with optional dependencies
try:
    from .monitoring import CacheMetrics, NoOpCollector

    try:
        from .monitoring import PrometheusCollector
    except ImportError:
        PrometheusCollector = None  # type: ignore
    try:
        from .monitoring import StatsDCollector
    except ImportError:
        StatsDCollector = None  # type: ignore
except ImportError:
    CacheMetrics = None  # type: ignore
    NoOpCollector = None  # type: ignore
    PrometheusCollector = None  # type: ignore
    StatsDCollector = None  # type: ignore

# Import vector search with optional dependencies
try:
    from .vector_search import RedisVectorSearch, VectorSimilaritySearch
except ImportError:
    VectorSimilaritySearch = None  # type: ignore
    RedisVectorSearch = None  # type: ignore

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
    # Backends (may be None if dependencies not installed)
    "CacheBackend",
    "RedisBackend",
    "MemoryBackend",
    "MemcachedBackend",
    # Monitoring (may be None if dependencies not installed)
    "CacheMetrics",
    "NoOpCollector",
    "PrometheusCollector",
    "StatsDCollector",
    # Vector search (may be None if dependencies not installed)
    "VectorSimilaritySearch",
    "RedisVectorSearch",
]
