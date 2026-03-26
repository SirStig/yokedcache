# Backends

YokedCache provides a unified API across all backends. Switching from memory to Redis doesn't change your application code—only the `CacheConfig`.

---

## Choosing a backend

| | Memory | Redis | Memcached | Disk | SQLite |
|--|--------|-------|-----------|------|--------|
| **Extra needed** | none | `redis` | `memcached` | `disk` | `sqlite` |
| **Shared across processes** | No | Yes | Yes | No (filesystem) | No (filesystem) |
| **Shared across machines** | No | Yes | Yes | No | No |
| **Persistent across restarts** | No | Optional | No | Yes | Yes |
| **Latency** | <1 µs | 0.1–10 ms | 0.5–2 ms | 1–10 ms | 1–5 ms |
| **Max throughput** | 1M+ ops/s | 100K+ ops/s | 50K+ ops/s | 10K+ ops/s | 5K+ ops/s |
| **Tags** | Yes | Yes | Limited | Yes | Yes |
| **Fuzzy search** | Yes | Yes | No | Yes | Yes |
| **Best for** | Dev, tests, single-process | Production, multi-process | Simple distributed | Long-lived local data | Local persistence |

**Rule of thumb:**
- Development / testing → **Memory** (no setup)
- Production, multi-server → **Redis** (the standard choice)
- Already have Memcached → **Memcached**
- Need local persistence on a single machine → **SQLite** or **Disk**

---

## Memory backend

Built-in, no extra installation needed. Uses LRU eviction when full.

```python
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

# Default—memory backend activates when no redis_url is set
cache = YokedCache(CacheConfig())
```

**Configuration:**

```python
config = CacheConfig(
    memory_max_size=10000,        # max entries before LRU eviction (default: 10000)
    memory_cleanup_interval=300,  # seconds between expired-key sweeps (default: 300)
)
```

**When to use:**
- Development and testing
- Single-process apps that don't need to share cache across workers
- Unit tests (no external services required)

**Test fixture pattern:**

```python
import pytest
from yokedcache import YokedCache, CacheConfig

@pytest.fixture
async def cache():
    c = YokedCache(CacheConfig())
    await c.connect()
    yield c
    await c.disconnect()
```

---

## Redis backend

The standard choice for production. Requires `pip install "yokedcache[redis]"` and a Redis 6+ server.

```bash
pip install "yokedcache[redis]"
```

### Connection

```python
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

# Via URL (simplest)
cache = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))

# Via environment variable
# export YOKEDCACHE_REDIS_URL=redis://localhost:6379/0
cache = YokedCache.from_env()
```

### URL formats

```
redis://localhost:6379/0                          # basic
redis://:password@localhost:6379/0               # password auth
redis://username:password@localhost:6379/0       # ACL user
rediss://hostname:6380/0                         # TLS (note the extra 's')
redis+sentinel://s1:26379,s2:26379/mymaster/0   # Sentinel
```

### Connection pool

Redis connections are pooled automatically. Tune for your app's concurrency:

```python
config = CacheConfig(
    redis_url="redis://...",
    max_connections=50,                      # pool size (default: 50)
    connection_pool_kwargs={
        "socket_connect_timeout": 5,         # seconds to connect
        "socket_timeout": 5,                 # seconds for read/write
        "socket_keepalive": True,            # keep connections alive
        "retry_on_timeout": True,            # retry on timeout
        "health_check_interval": 30,         # background health ping (seconds)
    },
)
```

### TLS (production)

Use `rediss://` (double-s) for encrypted connections. Managed Redis services like AWS ElastiCache, Azure Cache for Redis, and GCP Memorystore all use TLS:

```python
config = CacheConfig(
    redis_url="rediss://my-redis.cache.amazonaws.com:6380/0",
    connection_pool_kwargs={
        "ssl_cert_reqs": "required",
        "ssl_ca_certs": "/path/to/ca.crt",
        "ssl_check_hostname": True,
    },
)
```

### Authentication

```python
# Password only
config = CacheConfig(redis_url="redis://:mypassword@host:6379/0")

# ACL user (Redis 6+)
config = CacheConfig(redis_url="redis://yokedcache_user:password@host:6379/0")
```

Create an ACL user with minimal permissions:

```redis
ACL SETUSER yokedcache on >password ~yokedcache:* +@read +@write +del +expire
```

### Redis server tuning (redis.conf)

```redis
# Memory
maxmemory 2gb
maxmemory-policy allkeys-lru   # evict LRU keys when full

# Network
tcp-keepalive 300
tcp-nodelay yes
timeout 0

# Optional persistence (comment out for pure cache)
# save 900 1
# save 300 10
```

### Starting Redis locally

```bash
# Docker (easiest)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# macOS
brew install redis && brew services start redis

# Ubuntu/Debian
sudo apt install redis-server && sudo systemctl start redis-server

# Verify
redis-cli ping   # should return PONG
yokedcache ping  # should show OK
```

### Cloud Redis

| Provider | URL format |
|----------|-----------|
| AWS ElastiCache | `rediss://cluster.abc.cache.amazonaws.com:6380/0` |
| Azure Cache for Redis | `rediss://myname.redis.cache.windows.net:6380/0` |
| GCP Memorystore | `redis://10.0.0.3:6379/0` (private IP) |
| Redis Cloud | `rediss://user:pass@redis-12345.cloud.redislabs.com:12345/0` |
| Upstash | `rediss://user:pass@us1-xxxx.upstash.io:6379/0` |

---

## Memcached backend

Lightweight distributed caching. Use when you already run Memcached or need its specific characteristics.

```bash
pip install "yokedcache[memcached]"
```

```python
from yokedcache.backends import MemcachedBackend
from yokedcache import YokedCache, CacheConfig

# Single server
backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="myapp")
cache = YokedCache(CacheConfig(backend=backend))

# Multiple servers with consistent hashing
backend = MemcachedBackend(
    servers=["cache1.example.com:11211", "cache2.example.com:11211"],
    behaviors={"ketama": True},  # consistent hashing (recommended for multi-node)
)
```

**Limitations vs Redis:**
- No native tag support (tags are emulated; may not work in all configurations)
- No persistence
- Max value size: 1 MB by default
- No built-in cluster or replication

**Starting Memcached locally:**

```bash
docker run -d --name memcached -p 11211:11211 memcached:alpine
```

---

## Disk backend (diskcache)

Local filesystem-backed persistence. Survives process restarts.

```bash
pip install "yokedcache[disk]"
```

> ⚠️ **Security warning:** The disk backend uses `diskcache`, which serializes with **pickle** by default. [CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) describes arbitrary code execution if an attacker can write to the cache directory. Keep the directory non-world-writable and don't use this on shared filesystems. See [Security](security.md).

```python
from yokedcache.backends import DiskCacheBackend
from yokedcache import YokedCache, CacheConfig

backend = DiskCacheBackend(directory="/var/cache/myapp", max_size_gb=5)
cache = YokedCache(CacheConfig(backend=backend))
```

---

## SQLite backend

Local persistence using SQLite. Slightly higher overhead than diskcache but avoids pickle.

```bash
pip install "yokedcache[sqlite]"
```

```python
from yokedcache.backends import SQLiteBackend
from yokedcache import YokedCache, CacheConfig

backend = SQLiteBackend(path="/var/cache/myapp/cache.db")
cache = YokedCache(CacheConfig(backend=backend))
```

---

## Per-prefix routing

Route different key prefixes to different backends. Useful for:

- Keeping hot data in memory while cold data lives in Redis
- Isolating session data to a dedicated Redis instance
- Using memory for dev while Redis is only used for specific prefixes

```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import MemoryBackend, RedisBackend

config = CacheConfig(
    # Default backend for all keys
    default_backend=RedisBackend(redis_url="redis://redis:6379/0"),

    # Per-prefix overrides
    prefix_backends={
        # "hot:*" keys go to in-process memory for sub-millisecond access
        "hot": MemoryBackend(max_size=1000),

        # "session:*" keys go to a dedicated Redis
        "session": RedisBackend(redis_url="redis://session-redis:6379/0"),

        # "analytics:*" keys go to a separate Redis DB
        "analytics": RedisBackend(redis_url="redis://redis:6379/1"),
    },
)

cache = YokedCache(config)

# Each prefix routes automatically:
await cache.set("hot:config", config_data, ttl=60)      # → memory
await cache.set("session:abc123", session, ttl=1800)     # → session Redis
await cache.set("user:42", user_data, ttl=300)           # → default Redis
```

---

## Environment-based backend selection

A common pattern is to use memory in development/tests and Redis in production:

```python
import os
from yokedcache import YokedCache, CacheConfig

# Falls back to memory if YOKEDCACHE_REDIS_URL is not set
cache = YokedCache(CacheConfig(redis_url=os.getenv("YOKEDCACHE_REDIS_URL")))
```

Or more explicit:

```python
import os
from yokedcache import YokedCache, CacheConfig

env = os.getenv("ENV", "development")
config = CacheConfig(
    redis_url="redis://..." if env == "production" else None,
    key_prefix=f"{env}_myapp",
)
cache = YokedCache(config)
```

---

## Backend health check

All backends expose the same health check API:

```python
is_healthy = await cache.health()
details = await cache.detailed_health_check()

print(details["status"])           # "healthy" or "unhealthy"
print(details["redis_connected"])  # True/False (Redis only)
print(details["connection_pool"])  # pool stats (Redis only)
```

CLI:

```bash
yokedcache ping
```
