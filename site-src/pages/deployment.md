# Deployment

Practical guide for running YokedCache in production.

---

## Checklist

Before going to production:

- [ ] Using Redis (not the memory backend)
- [ ] `redis_url` uses `rediss://` (TLS) if Redis isn't on localhost
- [ ] Redis is in a private network / VPC, not exposed to the internet
- [ ] `key_prefix` is set (avoids collisions if multiple apps share Redis)
- [ ] `allow_legacy_insecure_deserialization=False` set if you've migrated from 0.x
- [ ] Connection pool sized appropriately for your concurrency
- [ ] Circuit breaker enabled
- [ ] Monitoring configured (Prometheus or StatsD)
- [ ] Cache warming plan in place for cold starts
- [ ] Cache invalidation tested after writes

---

## Configuration

A production `CacheConfig`:

```python
import os
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

config = CacheConfig(
    redis_url=os.environ["REDIS_URL"],  # rediss://... for TLS
    default_ttl=300,
    key_prefix=os.getenv("CACHE_PREFIX", "myapp"),
    max_connections=50,

    # Resilience
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_timeout=60.0,
    connection_retries=3,
    retry_delay=0.1,
    fallback_enabled=True,

    # Connection tuning
    connection_pool_kwargs={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30,
    },

    # Security
    allow_legacy_insecure_deserialization=False,

    # Observability
    log_level="WARNING",
    enable_metrics=True,
    prometheus_port=9100,
)

cache = YokedCache(config)
```

Or via environment variables (useful in containerized environments):

```bash
YOKEDCACHE_REDIS_URL=rediss://user:pass@redis.example.com:6380/0
YOKEDCACHE_DEFAULT_TTL=300
YOKEDCACHE_KEY_PREFIX=prod_myapp
YOKEDCACHE_MAX_CONNECTIONS=50
YOKEDCACHE_ENABLE_CIRCUIT_BREAKER=true
YOKEDCACHE_LOG_LEVEL=WARNING
YOKEDCACHE_ENABLE_METRICS=true
```

---

## Redis configuration

### Server settings (redis.conf)

```redis
# Memory: evict LRU keys when full (appropriate for a cache)
maxmemory 4gb
maxmemory-policy allkeys-lru

# Network
tcp-keepalive 300
tcp-nodelay yes
timeout 0

# Optional: disable persistence for a pure cache (faster)
# save ""
# appendonly no
```

### Connection pool sizing

Rule of thumb: set `max_connections` to roughly your expected concurrent requests per process. For a FastAPI app running with 4 Uvicorn workers and 50 concurrent requests each, start with `max_connections=50` per worker.

Too small → connection wait time. Too large → Redis memory pressure from idle connections.

### Redis ACL (least-privilege)

```redis
ACL SETUSER yokedcache on >strongpassword
  ~yokedcache:*        ← can only touch keys with this prefix
  +@read               ← GET, MGET, EXISTS, TTL, etc.
  +@write              ← SET, MSET, DEL, EXPIRE, etc.
  +@sortedset          ← needed for tag operations
  +scan                ← needed for pattern invalidation
  -@dangerous          ← no FLUSHALL, CONFIG, etc.
```

---

## FastAPI lifecycle

Use the lifespan context manager to connect/disconnect cleanly:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig(...))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    yield
    await cache.disconnect()

app = FastAPI(lifespan=lifespan)
```

This ensures Redis connections are properly established before requests arrive and cleanly closed on shutdown.

---

## Multiple workers

Each Uvicorn/Gunicorn worker has its own connection pool, but they all share the same Redis. The cache is effectively shared across workers because they all read and write the same keys.

```bash
# With Uvicorn
uvicorn app:app --workers 4

# With Gunicorn + Uvicorn workers
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker
```

No special configuration needed. Each worker creates its own pool of `max_connections` connections.

---

## Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    environment:
      YOKEDCACHE_REDIS_URL: redis://redis:6379/0
      YOKEDCACHE_KEY_PREFIX: myapp
    depends_on:
      redis:
        condition: service_healthy

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

---

## Kubernetes

```yaml
# deployment.yaml
env:
  - name: YOKEDCACHE_REDIS_URL
    valueFrom:
      secretKeyRef:
        name: redis-secret
        key: url
  - name: YOKEDCACHE_KEY_PREFIX
    value: "prod_myapp"
  - name: YOKEDCACHE_MAX_CONNECTIONS
    value: "25"   # lower per-pod; many pods × 25 = reasonable total
  - name: YOKEDCACHE_ENABLE_METRICS
    value: "true"

# Readiness probe via health check endpoint
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

Health endpoint:

```python
@app.get("/health")
async def health():
    cache_ok = await cache.health()
    if not cache_ok:
        return JSONResponse({"status": "degraded"}, status_code=503)
    return {"status": "ok"}
```

---

## Cache warming after deploys

Cold caches after a deploy can spike database load. A few strategies:

**Pre-warm on startup:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    await warm_critical_data()
    yield
    await cache.disconnect()

async def warm_critical_data():
    config = await fetch_app_config()
    await cache.set("config:global", config, ttl=3600)

    top_users = await db.get_top_users(limit=100)
    await cache.set_many(
        {f"user:{u.id}": u.dict() for u in top_users},
        ttl=300,
    )
```

**CLI warm command:**

```bash
yokedcache warm --config-file warming.yaml
```

**Stale-while-revalidate:** Extend TTLs with `stale_ttl` so old values serve during re-population.

---

## Monitoring in production

See the full [Monitoring](monitoring.md) guide. At minimum, watch:

- **Hit rate** — should be >80% for most apps. Dropping hit rate = data is expiring too fast or invalidation is too aggressive
- **Operation latency** — p95 > 10ms for Redis often indicates network or pool exhaustion
- **Error rate** — any sustained errors need investigation
- **Memory** — as Redis approaches `maxmemory`, evictions increase and hit rate may drop

Quick CLI check:

```bash
yokedcache stats
```

---

## Security hardening

- Use TLS (`rediss://`): all traffic between your app and Redis is encrypted
- Place Redis in a private subnet / VPC: it should never be accessible from the internet
- Use Redis ACLs: give the cache user only the permissions it needs
- Set `allow_legacy_insecure_deserialization=False` once you've migrated away from 0.x entries
- Don't cache sensitive data unless encrypted at rest
- Rotate Redis credentials regularly; prefer per-service ACL users

See [Security](security.md) for the full threat model.
