# Usage Patterns

The core ways to read and write cache entries. For invalidation strategies, see [Invalidation](invalidation.md). For resilience patterns (circuit breaker, SWR, stale-if-error), see [Resilience](resilience.md).

---

## Decorator caching (`@cached`)

The simplest way to add caching. Works on both `async def` and plain `def`:

```python
from yokedcache import cached, YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig())

@cached(cache=cache, ttl=300, tags=["users"])
async def get_user(user_id: int):
    return await db.fetch_user(user_id)

# First call hits the database
user = await get_user(42)

# Same arguments → cache hit, no DB call
user = await get_user(42)

# Different arguments → separate cache entry, DB hit
other = await get_user(99)
```

### All decorator options

```python
@cached(
    cache=cache,                              # YokedCache instance (required)
    ttl=300,                                  # seconds until expiry
    tags=["users", "api_v2"],                # tags for group invalidation
    cache_key_prefix="api",                  # override the key namespace
    serialization=SerializationMethod.JSON,  # JSON (default), PICKLE, MSGPACK
    single_flight=True,                      # coalesce concurrent misses
    serve_stale_on_error=True,               # return stale value if backend fails
    stale_ttl=60,                            # extra seconds to keep stale value
)
async def get_user(user_id: int, include_prefs: bool = False):
    ...
```

### Sync functions

```python
@cached(cache=cache, ttl=600)
def load_config() -> dict:
    return json.load(open("config.json"))

config = load_config()   # first call: reads file
config = load_config()   # second call: from cache
```

### Bypassing the cache

Call the underlying function directly when you need fresh data:

```python
# These skip the cache:
result = await get_user.__wrapped__(42)
result = get_user.__wrapped__(42)  # sync version

# Or pass a flag through:
@cached(cache=cache, ttl=300)
async def get_user(user_id: int, bypass: bool = False):
    if bypass:
        return await get_user.__wrapped__(user_id)
    ...
```

### Cache key inspection

```python
# See what key would be generated for given args
key = get_user.cache_key(42, include_prefs=False)
print(key)  # "yokedcache:get_user:a3f8c2d1..."
```

---

## Manual operations

For cases where you need direct control over keys, values, or options.

### get / set / delete

```python
# Set a value
await cache.set("user:42", {"name": "Alice", "email": "alice@example.com"}, ttl=300)

# Get a value (returns None if missing or expired)
user = await cache.get("user:42")

# Get with a default
user = await cache.get("user:42") or {"name": "Guest"}

# Delete
await cache.delete("user:42")

# Check existence (does not reset TTL)
exists = await cache.exists("user:42")  # True or False
```

### Batch operations

Batch operations use pipelining internally for efficiency:

```python
# Set many at once
await cache.set_many(
    {
        "user:1": {"name": "Alice"},
        "user:2": {"name": "Bob"},
        "user:3": {"name": "Charlie"},
    },
    ttl=300,
    tags=["users"],
)

# Get many at once — returns a dict keyed by the input keys
results = await cache.get_many(["user:1", "user:2", "user:3"])
# {"user:1": {...}, "user:2": {...}, "user:3": None}  ← None if missing

# Delete many at once
await cache.delete_many(["user:1", "user:2"])
```

### Get-or-set pattern

A common pattern: check the cache, fall back to the source, store the result:

```python
async def get_user_cached(user_id: int):
    key = f"user:{user_id}"
    user = await cache.get(key)
    if user is None:
        user = await db.fetch_user(user_id)
        await cache.set(key, user, ttl=300)
    return user
```

Or use `get_or_set` if available:

```python
user = await cache.get_or_set(
    key=f"user:{user_id}",
    factory=lambda: db.fetch_user(user_id),
    ttl=300,
)
```

### TTL inspection

```python
# Remaining TTL in seconds (None if key doesn't exist)
ttl = await cache.ttl("user:42")
print(f"Expires in {ttl}s")

# Refresh TTL without changing the value
await cache.expire("user:42", ttl=600)
```

---

## FastAPI integration

### Dependency caching

`cached_dependency` wraps a FastAPI dependency. Reads are cached; writes auto-invalidate:

```python
from fastapi import FastAPI, Depends
from yokedcache import YokedCache, cached_dependency
from yokedcache.config import CacheConfig
from contextlib import asynccontextmanager

cache = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    yield
    await cache.disconnect()

app = FastAPI(lifespan=lifespan)

# Wrap the dependency—table_name controls which tag to invalidate on commit
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    return db.query(User).filter(User.id == user_id).first()

@app.post("/users")
async def create_user(data: UserCreate, db=Depends(cached_get_db)):
    user = User(**data.dict())
    db.add(user)
    await db.commit()  # ← this invalidates "table:users" automatically
    return user
```

### Multiple table dependencies

```python
# Different dependencies for different tables
cached_users_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")
cached_orders_db = cached_dependency(get_db, cache=cache, ttl=60, table_name="orders")

@app.get("/users/{user_id}/orders")
async def get_user_orders(
    user_id: int,
    users_db=Depends(cached_users_db),
    orders_db=Depends(cached_orders_db),
):
    user = users_db.query(User).filter(User.id == user_id).first()
    orders = orders_db.query(Order).filter(Order.user_id == user_id).all()
    return {"user": user, "orders": orders}
```

### Caching non-database dependencies

`cached_dependency` works on any FastAPI dependency, not just databases:

```python
def get_feature_flags():
    return load_flags_from_remote()

cached_flags = cached_dependency(get_feature_flags, cache=cache, ttl=60)

@app.get("/features")
async def features(flags=Depends(cached_flags)):
    return flags
```

### Route-level caching with `@cached`

```python
@app.get("/products/top")
@cached(cache=cache, ttl=300, tags=["products"])
async def top_products():
    return await db.fetch_top_products(limit=20)
```

---

## Listing and inspecting keys

```python
# All keys matching a pattern
keys = await cache.get_keys_by_pattern("user:*")

# All keys (use with care on large caches)
all_keys = await cache.get_all_keys()

# Key metadata
meta = await cache.get_meta("user:42")
# {"key": "user:42", "ttl": 247, "tags": ["users"], "size_bytes": 128}
```

From the CLI:

```bash
yokedcache list --pattern "user:*"
yokedcache list --tags users
yokedcache list --include-values --format json
```

---

## Stats and health

```python
# In-process stats
stats = await cache.get_stats()
print(f"Hit rate:   {stats.hit_rate:.1%}")
print(f"Keys:       {stats.key_count}")
print(f"Memory:     {stats.memory_usage_mb:.1f} MB")
print(f"Total ops:  {stats.total_operations}")

# Health check
is_healthy = await cache.health()              # bool
details = await cache.detailed_health_check()  # dict with connection, pool, etc.
```

From the CLI:

```bash
yokedcache stats
yokedcache stats --watch          # live refresh every 2s
yokedcache stats --format json    # machine-readable
```

---

## Fuzzy search

Find keys by approximate match (requires `yokedcache[fuzzy]`):

```python
results = await cache.fuzzy_search(
    query="alice",
    threshold=80,        # similarity score 0–100 (default: 80)
    max_results=10,
    tags={"users"},      # restrict search to this tag
)
for r in results:
    print(r.key, r.score, r.value)
```

CLI:

```bash
yokedcache search "alice" --threshold 80 --tags users
```

See [Vector Search](vector-search.md) for semantic similarity search.

---

## Cache warming

Pre-populate the cache before traffic arrives. Avoids cold-start misses after a deploy.

```python
from yokedcache import warm_cache

await warm_cache(cache, [
    {"key": "config:global", "value": await fetch_config(), "ttl": 3600},
    {"key": "categories", "value": await fetch_categories(), "ttl": 7200},
])
```

Or run concurrently:

```python
import asyncio

async def warm():
    top_ids = await db.get_top_user_ids(limit=100)
    await asyncio.gather(*[get_user(uid) for uid in top_ids])

asyncio.run(warm())
```

CLI:

```bash
yokedcache warm --config-file warming.yaml --verbose
```

---

## HTTP cache middleware

Add `ETag` / `Cache-Control` headers at the HTTP layer (requires `yokedcache[web]`):

```bash
pip install "yokedcache[web]"
```

```python
from yokedcache.middleware import HTTPCacheMiddleware

app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,
    # key_builder is required for authenticated routes to avoid leaking responses
    key_builder=lambda req: f"{req.url}:{req.headers.get('x-user-id', 'anon')}",
)
```

See [Middleware](middleware.md) for the full reference.

---

## Sync equivalents

Every async method has a `*_sync` counterpart for use in blocking contexts:

| Async | Sync |
|-------|------|
| `await cache.get(key)` | `cache.get_sync(key)` |
| `await cache.set(key, val, ttl)` | `cache.set_sync(key, val, ttl)` |
| `await cache.delete(key)` | `cache.delete_sync(key)` |
| `await cache.exists(key)` | `cache.exists_sync(key)` |
| `await cache.invalidate_tags([...])` | `cache.invalidate_tags_sync([...])` |
| `await cache.invalidate_pattern(p)` | `cache.invalidate_pattern_sync(p)` |
| `await cache.get_many(keys)` | `cache.get_many_sync(keys)` |
| `await cache.set_many({...})` | `cache.set_many_sync({...})` |

Don't call `*_sync` from inside a running event loop. Use `await` there instead.
