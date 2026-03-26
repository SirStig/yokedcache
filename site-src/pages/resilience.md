# Resilience

YokedCache includes several patterns to keep your app running when the cache behaves unexpectedly—backend outages, high latency, cache stampedes, and stale data.

---

## Graceful degradation (default)

By default, cache failures don't surface to your application. If a `get` or `set` throws a connection error, the decorated function runs normally and returns real results. The error is logged at `WARNING` level but not re-raised.

```python
@cached(cache=cache, ttl=300)
async def get_user(user_id: int):
    # If Redis is down, this still runs and returns real data
    return await db.fetch_user(user_id)
```

To disable this and let cache errors propagate:

```python
config = CacheConfig(fallback_enabled=False)
```

---

## Circuit breaker

The circuit breaker prevents your app from hammering a broken cache backend on every request. After a configured number of consecutive failures, it "opens" and bypasses the cache entirely until the backend recovers.

```python
config = CacheConfig(
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,   # open after N consecutive failures
    circuit_breaker_timeout=60.0,          # seconds before trying again
)
cache = YokedCache(config)
```

**States:**

```
Closed ──N failures──▶ Open ──timeout──▶ Half-Open ──success──▶ Closed
  ▲                                           │
  └──────────────── failure ──────────────────┘
```

| State | Behavior |
|-------|----------|
| **Closed** | Normal—reads and writes go to the backend |
| **Open** | Cache bypassed—all requests go directly to the underlying function |
| **Half-open** | One test request goes to the backend; if it succeeds, circuit closes |

Monitor circuit breaker state:

```python
details = await cache.detailed_health_check()
print(details["circuit_breaker"])  # {"state": "closed", "failure_count": 0}
```

---

## Retries

Transient errors (network hiccup, Redis restart) often resolve on their own. Configure retries to handle them:

```python
config = CacheConfig(
    connection_retries=3,
    retry_delay=0.1,   # base delay in seconds (with exponential backoff)
)
```

Backoff schedule for `retry_delay=0.1`: 0.1s → 0.2s → 0.4s.

---

## Stale-while-revalidate

Serve the cached value immediately (even if expired), and refresh in the background. The user gets a fast response; the cache gets updated before the next request:

```python
@cached(
    cache=cache,
    ttl=300,       # entry "freshness" window
    stale_ttl=60,  # extra seconds to keep serving stale after ttl expires
)
async def get_product_catalog():
    return await db.fetch_catalog()
```

How it works:
1. Entry is fresh (within `ttl`): return cached value
2. Entry is stale (within `ttl + stale_ttl`): return cached value immediately, trigger background refresh
3. Entry is gone (beyond `ttl + stale_ttl`): synchronous cache miss, wait for refresh

This eliminates the latency spike on cache miss for popular entries.

---

## Stale-if-error

Return the last known value if the underlying data source fails, rather than surfacing an error to the user:

```python
@cached(
    cache=cache,
    ttl=300,
    serve_stale_on_error=True,  # return stale value if the function raises
)
async def get_external_data():
    return await external_api.fetch()  # might throw
```

If `get_external_data()` raises an exception, the last successfully cached value is returned instead. This is useful for external API calls where partial availability is better than a 500 error.

---

## Single-flight (request coalescing)

Without single-flight, if 50 requests arrive simultaneously for an uncached key, all 50 will be cache misses and all 50 will hit your database at once. Single-flight ensures only one request runs; the other 49 wait and share its result:

```python
@cached(
    cache=cache,
    ttl=300,
    single_flight=True,  # coalesce concurrent misses for the same key
)
async def get_expensive_resource(resource_id: str):
    return await compute_expensive_thing(resource_id)
```

This prevents the **cache stampede** (thundering herd) problem on cache misses.

---

## Combining patterns

These patterns compose. A production-hardened function might use all of them:

```python
@cached(
    cache=cache,
    ttl=300,
    stale_ttl=60,           # serve stale for up to 60s after expiry
    serve_stale_on_error=True, # serve stale if the function raises
    single_flight=True,     # coalesce concurrent misses
    tags=["products"],
)
async def get_product(product_id: str):
    return await db.fetch_product(product_id)
```

---

## Connection resilience

Configure connection-level resilience separately from application-level patterns:

```python
config = CacheConfig(
    redis_url="redis://...",

    # Retry connection errors
    connection_retries=3,
    retry_delay=0.1,

    # Circuit breaker for sustained outages
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_timeout=60.0,

    # Keep connections alive
    connection_pool_kwargs={
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30,
    },

    # Fall back gracefully if all else fails
    fallback_enabled=True,
)
```

---

## Testing resilience

Test that your app behaves correctly when the cache is down:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_graceful_degradation():
    """App should still work when Redis is unreachable."""
    with patch.object(cache, "get", side_effect=ConnectionError("Redis is down")):
        result = await get_user(42)
        assert result is not None   # function ran normally despite cache error

@pytest.mark.asyncio
async def test_stale_on_error():
    """App should serve stale data when the database is down."""
    # Warm the cache
    await cache.set("product:1", {"name": "Widget"}, ttl=300)

    with patch("db.fetch_product", side_effect=Exception("DB is down")):
        result = await get_product("1")
        assert result["name"] == "Widget"  # stale value returned
```
