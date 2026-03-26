# Performance

Practical tuning advice for getting the most out of YokedCache in production.

---

## Backend latency

Understanding your baseline latency helps you set expectations and diagnose problems:

| Backend | Typical GET latency | Notes |
|---------|---------------------|-------|
| Memory | < 1 µs | Limited to one process |
| Redis (same host) | 0.1–0.5 ms | Loopback network |
| Redis (local network) | 1–3 ms | LAN / same DC |
| Redis (cross-region) | 10–100 ms | WAN — cache at the edge instead |
| Memcached (local) | 0.5–2 ms | Similar to Redis |

If your Redis GET p95 is > 10ms on a local network, investigate:
- Connection pool exhaustion (increase `max_connections`)
- Large payloads (compress or paginate)
- Redis memory pressure / evictions
- Network congestion

---

## Connection pool sizing

Each `YokedCache` instance has a connection pool. The right size depends on your app's concurrency:

```python
config = CacheConfig(
    redis_url="...",
    max_connections=50,  # adjust based on concurrency
)
```

**Rule of thumb:** `max_connections ≈ expected concurrent requests per worker`. For a FastAPI app with 4 Uvicorn workers handling 50 concurrent requests each, 50 connections per worker is a good starting point.

**Symptoms of undersized pool:**
- Requests queuing to acquire a connection
- Elevated GET/SET latency under load
- `ConnectionPool exhausted` errors in logs

**Symptoms of oversized pool:**
- High Redis memory usage from idle connections
- Too many open file descriptors on the Redis server

---

## TTL strategy

| Data type | Suggested TTL | Reasoning |
|-----------|---------------|-----------|
| Static config | 1–24 hours | Almost never changes |
| Product catalog | 1–6 hours | Changes infrequently |
| User profiles | 5–60 min | Changes occasionally |
| Session data | 15–60 min | Per-user, moderate churn |
| Search results | 1–5 min | Freshness matters |
| Real-time aggregations | 10–60 sec | Tolerate slight staleness |
| Rate limit counters | Exact TTL | Accuracy critical |

**Jitter:** Keep TTL jitter enabled (default ±10%). It prevents synchronized expirations that would flood your DB simultaneously.

```python
# Custom jitter range
config = CacheConfig(ttl_jitter_percent=15.0)  # ±15%

# Disable (not recommended for high-traffic)
config = CacheConfig(ttl_jitter_percent=0)
```

---

## Key design

Smaller keys save memory and reduce network payload:

```python
# Good: compact but readable
"u:42"
"p:electronics:99"
"s:abc123"

# Fine: slightly longer but clearer
"user:42"
"product:99"
"session:abc123"

# Avoid: very long keys with redundant info
"myapp_production_user_data_user_id_42_full_profile"
```

**Avoid giant values.** Storing a 5 MB blob in a single cache entry means:
- 5 MB transferred on every cache miss
- 5 MB serialized/deserialized on every hit
- Other keys evicted earlier if Redis is near `maxmemory`

Instead, cache only what you need or paginate:

```python
# Cache individual items, not the whole list
await cache.set(f"product:{id}", product, ttl=3600)

# For lists, cache the IDs + fetch items individually
await cache.set("product_ids:electronics", [1, 2, 3, ...], ttl=300)
```

---

## Serialization speed

| Method | Speed | Size | Use when |
|--------|-------|------|----------|
| JSON | Medium | Largest | Default; interoperable; debuggable |
| MessagePack | Fast | Smaller | Binary data, cross-language |
| Pickle | Varies | Medium | Complex Python objects |

Benchmark with your actual data—the difference is often smaller than expected for typical payloads (< 10 KB). For payloads > 100 KB, consider enabling compression:

```python
config = CacheConfig(
    enable_compression=True,
    compression_threshold=1024,  # compress values > 1 KB
)
```

---

## Async vs sync

| Context | Recommended |
|---------|-------------|
| FastAPI / Starlette / Django async | `await cache.get()` |
| asyncio scripts | `await cache.get()` |
| Sync scripts, CLI tools | `cache.get_sync()` |
| Tight loops in sync code | Batch with `get_many_sync()` |

The `*_sync` methods run `asyncio.run()` per call—each creates a new event loop. This is fine for occasional use but has overhead in tight loops. If you need sync in a hot path, batch operations:

```python
# Instead of many individual sync calls:
for uid in user_ids:
    users[uid] = cache.get_sync(f"user:{uid}")  # overhead × N

# Use batch:
results = cache.get_many_sync([f"user:{uid}" for uid in user_ids])
```

---

## Batch operations

Batch operations use pipelining internally, making them much faster than looping:

```python
# Single round trip instead of N round trips
results = await cache.get_many(["user:1", "user:2", "user:3"])

await cache.set_many({
    "user:1": u1,
    "user:2": u2,
    "user:3": u3,
}, ttl=300)

await cache.delete_many(["old:1", "old:2", "old:3"])
```

---

## Redis server tuning

Add to `redis.conf`:

```redis
# Eviction policy for a cache (evict LRU keys when maxmemory is reached)
maxmemory 4gb
maxmemory-policy allkeys-lru

# Network
tcp-nodelay yes          # reduce latency
tcp-keepalive 300        # keep idle connections alive

# For pure cache (no persistence needed):
save ""
appendonly no

# Lazy freeing: free memory asynchronously (reduces blocking)
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
```

---

## Profiling cache impact

Compare response times with and without cache to measure impact:

```python
import time

# Time a cache miss
await cache.delete("user:42")
start = time.perf_counter()
await get_user(42)
miss_time = time.perf_counter() - start

# Time a cache hit
start = time.perf_counter()
await get_user(42)
hit_time = time.perf_counter() - start

print(f"Miss: {miss_time*1000:.1f}ms, Hit: {hit_time*1000:.1f}ms")
print(f"Speedup: {miss_time/hit_time:.0f}x")
```

---

## Common performance issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Hit rate drops suddenly | Aggressive invalidation or TTL too short | Review invalidation logic; increase TTL |
| GET latency spikes | Pool exhaustion or Redis memory pressure | Increase `max_connections`; add memory; enable eviction |
| High memory on Redis | Too many keys or large values | Enable LRU eviction; paginate large values; reduce TTL |
| Slow cold start | No cache warming | Warm critical data on startup |
| Frequent thundering herds | No jitter; no single-flight | Enable TTL jitter; use `single_flight=True` |
