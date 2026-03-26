"""
YokedCache — async caching with pluggable backends and tag-based invalidation.

Core installs use an in-memory store unless you add optional extras (e.g. ``redis``,
``web`` for Starlette HTTP middleware, ``memcached``, ``full``).
"""

__version__ = "1.0.1"
__author__ = "SirStig"
__email__ = "twogoodgamer2@gmail.com"
__license__ = "MIT"

try:
    from .cache import YokedCache
except ImportError as exc:
    _cache_import_error = exc

    class YokedCache:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Could not import YokedCache. Check core dependencies "
                "(orjson, pyyaml, click) or see the package README."
            ) from _cache_import_error


try:
    from .config import CacheConfig
except ImportError:
    # If PyYAML is not available, create a placeholder that gives helpful error
    class CacheConfig:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "PyYAML is required for CacheConfig. Please install with: "
                "pip install pyyaml>=6.0"
            )


from .decorators import cached, cached_dependency
from .exceptions import (
    CacheConnectionError,
    CacheKeyError,
    CacheSerializationError,
    YokedCacheError,
)
from .models import CacheEntry, CacheStats, InvalidationRule
from .utils import (
    deserialize_data,
    deserialize_from_cache,
    generate_cache_key,
    serialize_data,
    serialize_for_cache,
)

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

try:
    from .routing import PrefixRouter
except ImportError:
    PrefixRouter = None  # type: ignore

try:
    from .swr import SWRScheduler
except ImportError:
    SWRScheduler = None  # type: ignore

try:
    from .tracing import CacheTracer, initialize_tracing
except ImportError:
    CacheTracer = None  # type: ignore
    initialize_tracing = None  # type: ignore[assignment]

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
    "serialize_for_cache",
    "deserialize_from_cache",
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
    # New features (may be None if dependencies not installed)
    "PrefixRouter",
    "SWRScheduler",
    "CacheTracer",
    "initialize_tracing",
]
