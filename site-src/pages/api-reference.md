# API Reference

Complete reference for `YokedCache`, `CacheConfig`, decorators, and supporting types.

---

## YokedCache

The main class. Create one instance per application and reuse it.

```python
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(config: CacheConfig)
```

### Constructors

```python
# From CacheConfig
cache = YokedCache(CacheConfig(...))

# From environment variables
cache = YokedCache.from_env()

# From YAML file
cache = YokedCache.from_yaml("cache.yaml")
```

### Lifecycle

| Method | Description |
|--------|-------------|
| `await cache.connect()` | Connect to the backend. Must be called before any cache operations. |
| `await cache.disconnect()` | Close all connections gracefully. |

### Core operations

#### `get`

```python
value = await cache.get(key: str) -> Any | None
```

Returns the cached value or `None` if missing or expired.

```python
user = await cache.get("user:42")
if user is None:
    user = await db.fetch_user(42)
```

#### `set`

```python
await cache.set(
    key: str,
    value: Any,
    ttl: int | None = None,
    tags: list[str] | set[str] | None = None,
    serialization: SerializationMethod | None = None,
) -> bool
```

Stores a value. Returns `True` on success.

```python
await cache.set("user:42", {"name": "Alice"}, ttl=300, tags=["users"])
```

#### `delete`

```python
await cache.delete(key: str) -> bool
```

Deletes a key. Returns `True` if the key existed.

#### `exists`

```python
exists = await cache.exists(key: str) -> bool
```

Checks if a key exists without fetching the value.

#### `ttl`

```python
remaining = await cache.ttl(key: str) -> int | None
```

Returns remaining TTL in seconds, or `None` if the key doesn't exist.

#### `expire`

```python
await cache.expire(key: str, ttl: int) -> bool
```

Updates the TTL of an existing key without changing its value.

#### `get_or_set`

```python
value = await cache.get_or_set(
    key: str,
    factory: Callable[[], Awaitable[Any]],
    ttl: int | None = None,
    tags: list[str] | None = None,
) -> Any
```

Returns the cached value if present; otherwise calls `factory()`, caches the result, and returns it.

```python
user = await cache.get_or_set(
    key=f"user:{user_id}",
    factory=lambda: db.fetch_user(user_id),
    ttl=300,
    tags=["users"],
)
```

### Batch operations

#### `get_many`

```python
results = await cache.get_many(keys: list[str]) -> dict[str, Any | None]
```

Returns a dict mapping each key to its value (or `None` if missing).

```python
results = await cache.get_many(["user:1", "user:2", "user:3"])
# {"user:1": {...}, "user:2": {...}, "user:3": None}
```

#### `set_many`

```python
await cache.set_many(
    mapping: dict[str, Any],
    ttl: int | None = None,
    tags: list[str] | None = None,
) -> bool
```

```python
await cache.set_many({"user:1": u1, "user:2": u2}, ttl=300, tags=["users"])
```

#### `delete_many`

```python
await cache.delete_many(keys: list[str]) -> int
```

Deletes multiple keys. Returns count of deleted keys.

### Invalidation

#### `invalidate_tags`

```python
await cache.invalidate_tags(tags: list[str]) -> int
```

Invalidates all entries tagged with any of the given tags. Returns the count of invalidated entries.

```python
await cache.invalidate_tags(["users", "table:users"])
```

#### `invalidate_pattern`

```python
await cache.invalidate_pattern(pattern: str) -> int
```

Invalidates all keys matching a glob pattern. Returns the count of invalidated entries.

```python
await cache.invalidate_pattern("user:*")
await cache.invalidate_pattern("session:temp:*")
```

#### `flush_all`

```python
await cache.flush_all() -> bool
```

Clears all keys under the configured `key_prefix`. Does **not** flush the entire Redis database.

### Search

#### `fuzzy_search`

```python
results = await cache.fuzzy_search(
    query: str,
    threshold: int = 80,          # similarity score 0–100
    max_results: int = 100,
    tags: set[str] | None = None,
) -> list[FuzzySearchResult]
```

Requires `yokedcache[fuzzy]`.

```python
results = await cache.fuzzy_search("alice", threshold=75, tags={"users"})
for r in results:
    print(r.key, r.score, r.value)
```

`FuzzySearchResult` fields: `key: str`, `score: int`, `value: Any`.

### Key inspection

#### `get_keys_by_pattern`

```python
keys = await cache.get_keys_by_pattern(
    pattern: str,
    limit: int = 1000,
) -> list[str]
```

#### `get_all_keys`

```python
keys = await cache.get_all_keys(limit: int = 1000) -> list[str]
```

Returns all keys under the configured prefix.

#### `get_meta`

```python
meta = await cache.get_meta(key: str) -> dict | None
```

Returns metadata about a key: TTL, tags, size, serialization method.

### Monitoring

#### `health`

```python
is_healthy = await cache.health() -> bool
```

#### `detailed_health_check`

```python
info = await cache.detailed_health_check() -> dict
```

Returns:

```python
{
    "status": "healthy",          # or "unhealthy"
    "backend_type": "redis",
    "redis_connected": True,
    "connection_pool": {
        "available": 48,
        "in_use": 2,
        "max": 50,
    },
    "circuit_breaker": {
        "state": "closed",
        "failure_count": 0,
    },
    "hit_rate": 0.87,
    "uptime_seconds": 3600,
}
```

#### `get_stats`

```python
stats = await cache.get_stats() -> CacheStats
```

`CacheStats` fields:

| Field | Type | Description |
|-------|------|-------------|
| `hit_rate` | `float` | 0.0–1.0 |
| `miss_rate` | `float` | 0.0–1.0 |
| `total_operations` | `int` | Total get+set+delete count |
| `cache_hits` | `int` | Cumulative hits |
| `cache_misses` | `int` | Cumulative misses |
| `key_count` | `int` | Current number of keys |
| `memory_usage_mb` | `float` | Approximate memory usage |
| `uptime_seconds` | `int` | Seconds since connect |

### Sync equivalents

All async methods have `*_sync` counterparts:

```python
cache.get_sync(key)
cache.set_sync(key, value, ttl, tags)
cache.delete_sync(key)
cache.exists_sync(key)
cache.get_many_sync(keys)
cache.set_many_sync(mapping, ttl, tags)
cache.delete_many_sync(keys)
cache.invalidate_tags_sync(tags)
cache.invalidate_pattern_sync(pattern)
cache.flush_all_sync()
```

Don't call these from inside a running event loop.

---

## CacheConfig

All configuration lives here. Pass it to `YokedCache(config)`.

```python
from yokedcache.config import CacheConfig, TableCacheConfig
```

### Core

| Parameter | Type | Default | Env var |
|-----------|------|---------|---------|
| `redis_url` | `str \| None` | `None` (memory) | `YOKEDCACHE_REDIS_URL` |
| `default_ttl` | `int` | `300` | `YOKEDCACHE_DEFAULT_TTL` |
| `key_prefix` | `str` | `"yokedcache"` | `YOKEDCACHE_KEY_PREFIX` |
| `default_serialization` | `SerializationMethod` | `JSON` | `YOKEDCACHE_DEFAULT_SERIALIZATION` |
| `ttl_jitter_percent` | `float` | `10.0` | — |

### Connection

| Parameter | Type | Default | Env var |
|-----------|------|---------|---------|
| `max_connections` | `int` | `50` | `YOKEDCACHE_MAX_CONNECTIONS` |
| `connection_timeout` | `int` | `30` | `YOKEDCACHE_CONNECTION_TIMEOUT` |
| `connection_pool_kwargs` | `dict` | `{}` | — |

### Resilience

| Parameter | Type | Default | Env var |
|-----------|------|---------|---------|
| `fallback_enabled` | `bool` | `True` | `YOKEDCACHE_FALLBACK_ENABLED` |
| `connection_retries` | `int` | `3` | `YOKEDCACHE_CONNECTION_RETRIES` |
| `retry_delay` | `float` | `0.1` | — |
| `enable_circuit_breaker` | `bool` | `False` | `YOKEDCACHE_ENABLE_CIRCUIT_BREAKER` |
| `circuit_breaker_failure_threshold` | `int` | `5` | — |
| `circuit_breaker_timeout` | `float` | `60.0` | — |

### Features

| Parameter | Type | Default | Env var |
|-----------|------|---------|---------|
| `enable_fuzzy` | `bool` | `False` | `YOKEDCACHE_ENABLE_FUZZY` |
| `fuzzy_threshold` | `int` | `80` | `YOKEDCACHE_FUZZY_THRESHOLD` |
| `enable_compression` | `bool` | `False` | `YOKEDCACHE_ENABLE_COMPRESSION` |
| `compression_threshold` | `int` | `1024` | — |

### Memory backend

| Parameter | Type | Default |
|-----------|------|---------|
| `memory_max_size` | `int` | `10000` |
| `memory_cleanup_interval` | `int` | `300` |

### Monitoring

| Parameter | Type | Default | Env var |
|-----------|------|---------|---------|
| `enable_metrics` | `bool` | `False` | `YOKEDCACHE_ENABLE_METRICS` |
| `prometheus_port` | `int` | `8000` | `YOKEDCACHE_PROMETHEUS_PORT` |
| `statsd_host` | `str \| None` | `None` | `YOKEDCACHE_STATSD_HOST` |
| `statsd_port` | `int` | `8125` | `YOKEDCACHE_STATSD_PORT` |
| `log_level` | `str` | `"INFO"` | `YOKEDCACHE_LOG_LEVEL` |

### Per-table config

```python
config = CacheConfig(
    tables={
        "users": TableCacheConfig(
            ttl=3600,
            tags={"user_data"},
            serialization_method=SerializationMethod.JSON,
            enable_fuzzy=True,
            fuzzy_threshold=85,
            enable_compression=False,
        ),
    }
)
```

`TableCacheConfig` accepts: `ttl`, `tags`, `serialization_method`, `enable_fuzzy`, `fuzzy_threshold`, `enable_compression`, `compression_threshold`, `query_specific_ttls`.

---

## Decorators

### `@cached`

```python
from yokedcache import cached

@cached(
    cache: YokedCache,
    ttl: int | None = None,
    tags: list[str] | None = None,
    cache_key_prefix: str | None = None,
    serialization: SerializationMethod | None = None,
    single_flight: bool = False,
    serve_stale_on_error: bool = False,
    stale_ttl: int = 0,
)
```

Works on `async def` and plain `def`. The cache key is derived from the function name and all arguments.

```python
@cached(cache=cache, ttl=300, tags=["users"])
async def get_user(user_id: int) -> dict:
    ...

# Access the underlying unwrapped function
raw = get_user.__wrapped__

# Inspect the generated key without calling the function
key = get_user.cache_key(user_id=42)
```

### `cached_dependency`

```python
from yokedcache import cached_dependency

cached_dep = cached_dependency(
    dependency: Callable,
    cache: YokedCache,
    ttl: int = 300,
    table_name: str | None = None,
    tags: list[str] | None = None,
)
```

Returns a FastAPI-compatible dependency that caches the dependency's return value and auto-invalidates on session commits.

```python
cached_get_db = cached_dependency(
    get_db,
    cache=cache,
    ttl=300,
    table_name="users",
)
```

---

## SerializationMethod

```python
from yokedcache.models import SerializationMethod

SerializationMethod.JSON     # default, portable, handles common Python types
SerializationMethod.PICKLE   # any Python object; requires trusted storage
SerializationMethod.MSGPACK  # binary, compact; requires pip install msgpack
```

---

## Exceptions

```python
from yokedcache.exceptions import (
    CacheError,              # base exception
    CacheConnectionError,    # backend connection failure
    CacheSerializationError, # serialization/deserialization failure
    CacheKeyError,           # invalid key format
    ConfigValidationError,   # invalid CacheConfig
)
```

All inherit from `CacheError`. When `fallback_enabled=True` (the default), these are caught internally and logged—they don't propagate to your application code unless you set `fallback_enabled=False`.
