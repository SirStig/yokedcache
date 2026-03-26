# Core Concepts

Understanding how YokedCache works will help you make good decisions about keys, TTLs, tags, and serialization—and debug things when they don't behave as expected.

---

## Architecture

YokedCache is a thin wrapper that sits in front of a pluggable backend. Every read goes through the wrapper first; on a miss, it calls your function or query, stores the result, and returns it. On a hit, it skips the underlying call entirely.

```
Your app
   │
   ▼
YokedCache wrapper
   │   ├── cache hit?  ─── yes ──▶ return stored value
   │   └── cache miss? ─── no  ──▶ call function/query ──▶ store result ──▶ return
   │
   ▼
Backend (Memory / Redis / Memcached / Disk / SQLite)
```

The same wrapper API works across all backends. Switching from memory to Redis doesn't change your application code.

---

## Cache keys

### Automatic key generation

When you use `@cached` or `cached_dependency`, keys are generated automatically from:

- The configured `key_prefix` (default: `"yokedcache"`)
- The function name or table name
- A stable hash of the arguments

```
yokedcache:get_user:a3f8c2d1   ← prefix:function:hash_of_args
yokedcache:table:users:b9e4f721
```

Different arguments produce different hashes, so `get_user(1)` and `get_user(2)` never collide.

### Manual keys

For `cache.set()` / `cache.get()`, you pass the key directly:

```python
await cache.set("user:42", {"name": "Alice"}, ttl=300)
user = await cache.get("user:42")  # returns the dict or None
```

### Key prefix

The prefix namespaces all keys. This prevents collisions between different apps or environments sharing the same Redis database:

```python
config = CacheConfig(key_prefix="prod_myapp")  # all keys: "prod_myapp:..."
config = CacheConfig(key_prefix="staging_myapp")
```

Set it per environment via `YOKEDCACHE_KEY_PREFIX`.

### Key sanitization

Keys are automatically sanitized before storage—non-ASCII characters are encoded, length is capped, and dangerous patterns are removed. You generally don't need to think about this, but it means keys with special characters may look slightly different in Redis than what you passed in.

---

## TTL and expiration

Every cache entry has a TTL (time-to-live) in seconds. After that time, the entry expires and the next read is a miss.

### TTL priority

When multiple TTL sources are configured, the most specific wins:

```
Explicit TTL on the call              (highest priority)
  └── Table-specific TTL in CacheConfig
        └── Global default_ttl in CacheConfig
              └── Backend default           (lowest priority)
```

```python
# Global default
config = CacheConfig(default_ttl=300)

# Per-table override
config = CacheConfig(
    default_ttl=300,
    tables={"users": TableCacheConfig(ttl=3600)},
)

# Per-call override (highest priority)
await cache.set("key", value, ttl=60)
```

### Jitter

YokedCache adds random jitter to every TTL (default: ±10%). A 300s TTL becomes something between 270–330s.

This prevents the **thundering herd** problem: if many cache entries expire at exactly the same time, every entry becomes a miss simultaneously and your database gets flooded with requests at once. Jitter spreads out the expirations.

```python
# Disable jitter if you need exact TTLs (not recommended for high-traffic systems)
config = CacheConfig(ttl_jitter_percent=0)
```

### Choosing TTL values

| Data type | Suggested TTL |
|-----------|---------------|
| User sessions | 15–60 minutes |
| User profiles | 5–60 minutes |
| Product catalog | 1–24 hours |
| Config / feature flags | 5–30 minutes |
| Search results | 1–5 minutes |
| Aggregations / analytics | 10–60 minutes |
| Reference data (countries, categories) | 24 hours+ |

Hot data that changes often → short TTL. Stable reference data → long TTL.

---

## Tags

Tags let you group related cache entries and invalidate them together, regardless of their keys.

### Setting tags

```python
# Manual set
await cache.set(
    "product:1",
    product_data,
    ttl=600,
    tags=["products", "category:electronics", "tenant:acme"],
)

# Via decorator
@cached(cache=cache, ttl=300, tags=["users", "api_v2"])
async def get_user(user_id: int):
    ...
```

### Invalidating by tag

```python
# All entries tagged "products" are invalidated
await cache.invalidate_tags(["products"])

# Multiple tags—any entry with ANY of these tags is invalidated
await cache.invalidate_tags(["category:electronics", "tenant:acme"])
```

### Automatic tagging (cached_dependency)

When you use `cached_dependency(get_db, table_name="users")`, YokedCache automatically:

1. Tags all reads with `"table:users"`
2. Listens for `commit()` calls on the session
3. Calls `invalidate_tags(["table:users"])` on commit

You never have to manually track what to invalidate after a write.

### Tag design patterns

```python
# Per-table tags (automatic with cached_dependency)
"table:users"
"table:products"

# Per-entity tags (for fine-grained invalidation)
f"user:{user_id}"
f"product:{product_id}"

# Feature tags (for grouped invalidation)
"search_results"
"homepage_data"
"analytics"

# Tenant tags (for multi-tenant isolation)
f"tenant:{tenant_id}"
```

---

## Invalidation patterns

Beyond tags, YokedCache supports two other invalidation strategies:

### Pattern-based

Invalidates all keys matching a glob pattern:

```python
await cache.invalidate_pattern("user:*")          # all user keys
await cache.invalidate_pattern("session:temp:*")  # temporary sessions
await cache.invalidate_pattern("*:stale")         # anything marked stale
```

> **Note:** Pattern invalidation on Redis uses `SCAN` + `DEL`, which can be slow if you have millions of keys. Prefer tag-based invalidation for high-traffic systems.

### Manual delete

```python
await cache.delete("user:42")
await cache.delete_many(["user:42", "user:43", "user:44"])
```

---

## Serialization

Values are serialized before storage and deserialized on read. Three built-in methods:

### JSON (default)

Best for simple data types. Portable across languages and tools. YokedCache's JSON encoder handles common Python types automatically:

| Python type | JSON representation |
|-------------|---------------------|
| `datetime` | ISO 8601 string |
| `date` | ISO 8601 string |
| `Decimal` | String |
| `UUID` | String |
| `set` | Array |
| `bytes` | Base64 string |

```python
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

data = {
    "id": uuid4(),
    "price": Decimal("99.99"),
    "created_at": datetime.now(),
    "tags": {"featured", "sale"},
}

await cache.set("item", data)  # serializes transparently
result = await cache.get("item")  # deserializes back
```

### Pickle

Supports any Python object. Use when you need to cache complex ORM objects, custom classes, or anything that isn't JSON-serializable.

```python
from yokedcache.models import SerializationMethod

await cache.set("session", session_obj, serialization=SerializationMethod.PICKLE)
```

> **Security:** Only use pickle with backends you fully control (private Redis, local memory). Anyone who can write to your cache backend can execute arbitrary code via pickle. See [Security](security.md).

### MessagePack

Compact binary format. Faster than JSON for large or deeply nested data, and more space-efficient.

```python
await cache.set("bulk_data", large_dict, serialization=SerializationMethod.MSGPACK)
```

Requires `pip install "yokedcache[backends]"` or `pip install msgpack`.

### Setting serialization

```python
# Per call
await cache.set("key", value, serialization=SerializationMethod.PICKLE)

# Per table (via CacheConfig)
config = CacheConfig(
    tables={
        "sessions": TableCacheConfig(serialization_method=SerializationMethod.PICKLE),
        "products": TableCacheConfig(serialization_method=SerializationMethod.MSGPACK),
    }
)

# Global default
config = CacheConfig(default_serialization=SerializationMethod.JSON)
```

---

## Error handling and resilience

### Graceful degradation

By default, cache failures don't crash your app. If `cache.get()` throws, the decorated function still runs and returns a real result. The error is logged but not re-raised.

```python
@cached(cache=cache, ttl=300)
async def get_data():
    # If Redis is down, this function still runs normally
    return await fetch_from_database()
```

Set `fallback_enabled=False` on `CacheConfig` if you want cache errors to propagate.

### Circuit breaker

For sustained failures (Redis is fully down), the circuit breaker prevents your app from repeatedly trying the cache and failing:

```python
config = CacheConfig(
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,   # open after 5 consecutive failures
    circuit_breaker_timeout=60.0,          # try again after 60 seconds
)
```

States:
- **Closed** — normal operation
- **Open** — cache bypassed, all requests go to the underlying function
- **Half-open** — testing if the backend has recovered

### Retries

```python
config = CacheConfig(
    connection_retries=3,
    retry_delay=0.1,  # seconds (with exponential backoff)
)
```

---

## Connection lifecycle

Always connect before using the cache and disconnect when done:

```python
# Script usage
cache = YokedCache(CacheConfig())
asyncio.run(cache.connect())

# ... use cache ...

asyncio.run(cache.disconnect())
```

In FastAPI, use the lifespan context manager:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    yield
    await cache.disconnect()

app = FastAPI(lifespan=lifespan)
```

---

## Async vs sync

| Context | Use |
|---------|-----|
| Inside FastAPI, Starlette, Django async views, asyncio | `await cache.get(...)`, `await cache.set(...)` |
| Scripts, blocking functions, sync code | `cache.get_sync(...)`, `cache.set_sync(...)` |
| `def` functions | `@cached` (auto-detects sync) |

The sync helpers internally run `asyncio.run()`, which creates a new event loop per call. This works fine for occasional use (scripts, startup tasks) but has overhead in tight loops. Prefer `await` in any context that already runs an event loop.

Available sync methods: `get_sync`, `set_sync`, `delete_sync`, `exists_sync`, `invalidate_tags_sync`, `invalidate_pattern_sync`.
