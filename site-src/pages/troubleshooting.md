# Troubleshooting & FAQ

---

## Debugging tools

```bash
# Is the cache reachable?
yokedcache ping

# What's in there?
yokedcache list --pattern "user:*"
yokedcache list --tags users

# What's the current hit rate?
yokedcache stats

# Search by approximate key
yokedcache search "alice" --threshold 70

# Get detailed health info
yokedcache ping --show-timing
```

Enable verbose logging in your app:

```python
import logging
logging.getLogger("yokedcache").setLevel(logging.DEBUG)
```

---

## Cache not updating after writes

**Symptom:** You update a record in the database but reads still return the old value.

**Causes and fixes:**

1. **Not using `cached_dependency`:** If you're using `@cached` or manual `cache.set()`, YokedCache doesn't know about your writes. You need to call `invalidate_tags()` manually after writes:

   ```python
   await db.update_user(user_id, data)
   await cache.invalidate_tags(["table:users"])
   ```

2. **`cached_dependency` but no `table_name`:** Specify the table name so YokedCache knows what to invalidate:

   ```python
   # Wrong
   cached_get_db = cached_dependency(get_db, cache=cache, ttl=300)

   # Right
   cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")
   ```

3. **Not calling `commit()`:** Auto-invalidation fires on `commit()`. If you're using `flush()` or bypassing the session, invalidation won't trigger.

4. **Wrong tag name:** Verify the tag used when writing matches the tag used when invalidating:

   ```python
   # Set
   await cache.set("key", value, tags=["users"])  # tag: "users"

   # Must match
   await cache.invalidate_tags(["users"])          # ✓
   await cache.invalidate_tags(["user_data"])      # ✗ — wrong tag
   ```

---

## Redis connection errors

**Symptom:** `ConnectionRefusedError`, `ConnectionError`, or `TimeoutError` in logs.

**Check:**

```bash
# Is Redis running?
redis-cli ping            # should return PONG
docker ps | grep redis    # if using Docker

# Can YokedCache connect?
yokedcache ping
yokedcache ping --redis-url redis://your-host:6379/0
```

**Common causes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` | Redis not running | Start Redis |
| `Authentication failed` | Wrong password/ACL | Check `redis_url` credentials |
| `SSL handshake failed` | TLS misconfiguration | Verify `ssl_cert_reqs` and CA cert path |
| `Timeout` | Network latency or pool exhaustion | Increase `max_connections`; check network |
| `Max clients reached` | Too many connections to Redis | Reduce `max_connections`; check for connection leaks |

**Connection pool exhaustion:** If you're hitting pool limits, reduce `max_connections` (connection leak) or increase it (legitimate concurrency):

```python
config = CacheConfig(
    redis_url="redis://...",
    max_connections=100,  # increase if legitimate concurrency
    connection_pool_kwargs={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
    },
)
```

---

## Serialization errors

**Symptom:** `CacheSerializationError` or `JSONDecodeError` when reading from cache.

**Cause 1: Object not JSON-serializable**

```python
# This fails with the default JSON serializer
await cache.set("key", MyCustomClass())

# Fix: serialize to a dict first
await cache.set("key", my_obj.to_dict())

# Or switch to pickle
from yokedcache.models import SerializationMethod
await cache.set("key", my_obj, serialization=SerializationMethod.PICKLE)
```

**Cause 2: Serialization mismatch (writer vs reader)**

If you write with pickle but read expecting JSON (or vice versa), deserialization fails. The typed envelope (1.x) includes the serialization method, so this should be caught automatically—but if you see this, check that both sides use the same `CacheConfig`.

**Cause 3: Legacy 0.x entries**

If `allow_legacy_insecure_deserialization=False` is set but you have entries written by 0.x, they'll be rejected. Clear those entries or temporarily re-enable legacy mode while migrating:

```bash
yokedcache flush --pattern "*" --force  # nuclear option
```

---

## Keys not found after being set

**Check key prefix:** Producer and consumer must use the same `key_prefix`:

```python
# Service A (writes)
cache_a = YokedCache(CacheConfig(key_prefix="myapp"))

# Service B (reads)—must match
cache_b = YokedCache(CacheConfig(key_prefix="myapp"))    # ✓
cache_b = YokedCache(CacheConfig(key_prefix="service_b")) # ✗ — different namespace
```

**Check TTL:** The key may have expired. Use `yokedcache list` to see what's there, or `cache.ttl(key)` to check remaining TTL.

**Check patterns:** Fuzzy search uses `fuzzy_threshold`—keys might exist but score below the threshold. Lower it to see more results:

```python
results = await cache.fuzzy_search("key_name", threshold=50)  # lower = broader
```

---

## Low hit rate

**Symptom:** Hit rate is lower than expected.

**Diagnose:**

```bash
yokedcache stats --watch  # watch hit rate over time
```

**Common causes:**

1. **TTL too short:** Entries expire before they can be reused. Increase `default_ttl` or per-table TTL.

2. **Over-invalidation:** Tags being invalidated too broadly or too often. Audit your `invalidate_tags()` calls.

3. **Cache warming needed:** After a restart, the cache is cold. Implement cache warming on startup.

4. **Key variability:** If cache keys include highly variable parameters (e.g., pagination offsets, random IDs), each unique combination is a separate cache entry and each is only hit once.

5. **Multiple instances with different prefixes:** Multiple services or app instances using different `key_prefix` values won't share cache entries.

---

## High memory usage on Redis

**Check:**

```bash
redis-cli info memory
yokedcache stats  # check key count and size
```

**Fixes:**

1. **Enable eviction:** Set `maxmemory-policy allkeys-lru` in `redis.conf` so Redis evicts old keys automatically.

2. **Shorter TTLs:** Reduce TTL for data that doesn't need to be cached as long.

3. **Compress large values:**

   ```python
   config = CacheConfig(enable_compression=True, compression_threshold=1024)
   ```

4. **Paginate large values:** Instead of caching a 10 MB response, cache individual items.

---

## Works without FastAPI?

Yes. `@cached` and `YokedCache` work in any Python context:

```python
# Script
import asyncio
from yokedcache import YokedCache, cached
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig())

@cached(cache=cache, ttl=300)
async def get_data():
    return expensive_operation()

asyncio.run(cache.connect())
result = asyncio.run(get_data())
asyncio.run(cache.disconnect())
```

`cached_dependency` and `HTTPCacheMiddleware` are FastAPI/Starlette-specific, but the core API is framework-agnostic.

---

## Works with Django async views?

Yes. Django 4.1+ supports async views. Use `await` as normal:

```python
from django.http import JsonResponse
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))

async def my_view(request):
    data = await cache.get("my_key")
    if data is None:
        data = await fetch_data()
        await cache.set("my_key", data, ttl=300)
    return JsonResponse(data)
```

Connect/disconnect using Django's `AppConfig.ready()` or a middleware.

---

## Disabling caching for a specific call

```python
# Call the unwrapped function directly
result = await get_user.__wrapped__(user_id)

# Or use ttl=0
await cache.set("key", value, ttl=0)  # expires immediately

# Or bypass via a parameter
@cached(cache=cache, ttl=300)
async def get_user(user_id: int):
    ...

# In tests, patch the cache.get to always return None
```

---

## How do I warm the cache?

```python
# Programmatic
from yokedcache import warm_cache

await warm_cache(cache, [
    {"key": "config:global", "value": await fetch_config(), "ttl": 3600},
])

# Or call the @cached functions directly on startup
await get_product_catalog()  # warms the cache as a side effect
```

CLI:

```bash
yokedcache warm --config-file warming.yaml
```

See [Deployment](deployment.md) for warming strategies.

---

## How do I see what's cached?

```bash
# CLI
yokedcache list
yokedcache list --pattern "user:*"
yokedcache list --include-values --format json

# In code
keys = await cache.get_all_keys()
meta = await cache.get_meta("user:42")  # TTL, tags, size
```
