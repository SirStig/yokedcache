---
title: Getting Started
description: Install YokedCache and run your first cache in minutes. Covers async, sync, FastAPI, configuration, and what to try next.
keywords: yokedcache, installation, getting started, async cache, sync, redis, fastapi
---

# Getting Started

YokedCache works out of the box with an in-process memory backend—no Redis required to try it. The main API is async (`await cache.get(...)`), but sync helpers (`get_sync` / `set_sync` / `@cached` on a plain `def`) are available for scripts or blocking code, and they run the same implementation underneath.

---

## Install

```bash
pip install yokedcache
```

That's it for local development and single-process apps. The memory backend is built in.

**For Redis** (recommended for production and multi-process apps):

```bash
pip install "yokedcache[redis]"
```

### Extras

| Extra | What it adds |
|-------|-------------|
| `redis` | Redis backend via `redis-py` |
| `web` | Starlette `HTTPCacheMiddleware` |
| `backends` | Disk, SQLite, Memcached backends |
| `observability` | Prometheus, StatsD, OpenTelemetry |
| `fuzzy` | Fuzzy key search |
| `vector` | TF-IDF vector similarity search |
| `sqlalchemy` | SQLAlchemy session helpers |
| `full` | Everything above |

Mix extras freely:

```bash
pip install "yokedcache[redis,observability]"
pip install "yokedcache[redis,fuzzy,vector]"
pip install "yokedcache[full]"
```

### Python version

YokedCache 1.x requires **Python 3.10+**, tested on 3.10 through 3.14. If you're stuck on Python 3.9, pin `yokedcache==0.3.0` temporarily—that branch doesn't receive security fixes from 1.x.

---

## First cache (async)

```python
import asyncio
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

async def main():
    cache = YokedCache(CacheConfig())  # in-process memory
    await cache.connect()

    await cache.set("greeting", "hello world", ttl=60)
    value = await cache.get("greeting")
    print(value)  # "hello world"

    await cache.disconnect()

asyncio.run(main())
```

To switch to Redis, just add `redis_url`:

```python
config = CacheConfig(redis_url="redis://localhost:6379/0")
```

Or set the env var `YOKEDCACHE_REDIS_URL` and leave `CacheConfig()` empty.

---

## Sync code

The `*_sync` helpers are backed by the same async implementation. Use them from scripts or blocking contexts where there's no running event loop:

```python
import asyncio
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig())
asyncio.run(cache.connect())

cache.set_sync("user:1", {"name": "Ada"}, ttl=300)
user = cache.get_sync("user:1")
print(user)  # {'name': 'Ada'}

exists = cache.exists_sync("user:1")
print(exists)  # True

cache.delete_sync("user:1")
asyncio.run(cache.disconnect())
```

> **Don't call `*_sync` from inside a running event loop.** Use `await` there instead. Each `*_sync` call internally spins up an event loop, so calling it from async code will raise a `RuntimeError`.

---

## Decorator caching

The `@cached` decorator caches the return value of a function. Works on both `async def` and plain `def`:

```python
import asyncio
from yokedcache import cached, YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig())

@cached(cache=cache, ttl=300, tags=["users"])
async def get_user(user_id: int):
    print(f"Fetching user {user_id}...")  # Only prints on cache miss
    return {"id": user_id, "name": f"User {user_id}"}

async def main():
    await cache.connect()

    u1 = await get_user(42)   # miss — prints the fetch message
    u2 = await get_user(42)   # hit — returns immediately, no print
    print(u1 == u2)           # True

    await cache.disconnect()

asyncio.run(main())
```

The cache key is derived from the function name and all arguments automatically. Different arguments = different cache entries.

```python
# These are cached separately:
await get_user(1)    # key: "yokedcache:get_user:<hash of (1,)>"
await get_user(2)    # key: "yokedcache:get_user:<hash of (2,)>"
```

### Sync function caching

```python
@cached(cache=cache, ttl=300)
def expensive_computation(n: int) -> int:
    return sum(range(n))
```

---

## FastAPI

```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
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

# Wrap the database dependency—reads are cached, writes auto-invalidate
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(cached_get_db)):
    return db.query(User).filter(User.id == user_id).first()

@app.post("/users")
async def create_user(data: UserCreate, db: Session = Depends(cached_get_db)):
    user = User(**data.dict())
    db.add(user)
    await db.commit()  # automatically invalidates the "table:users" tag
    return user
```

See the [FastAPI tutorial](tutorials/fastapi.md) for a complete working app.

---

## Tags and invalidation

Tags let you group entries and clear them all at once:

```python
await cache.set("product:1", p1, ttl=600, tags=["products", "electronics"])
await cache.set("product:2", p2, ttl=600, tags=["products", "books"])

# Clear everything tagged "products"
await cache.invalidate_tags(["products"])

# Clear only electronics
await cache.invalidate_tags(["electronics"])

# Pattern-based (by key prefix)
await cache.invalidate_pattern("product:*")
```

---

## Configuration

Three ways to configure—they compose together:

```python
# Programmatic
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig(
    redis_url="redis://localhost:6379/0",
    default_ttl=300,
    key_prefix="myapp",
))

# From environment variables (YOKEDCACHE_REDIS_URL, YOKEDCACHE_DEFAULT_TTL, etc.)
cache = YokedCache.from_env()

# From YAML file
cache = YokedCache.from_yaml("cache.yaml")
```

See [Configuration](configuration.md) for the full reference.

---

## CLI

A built-in CLI is useful for debugging, inspection, and ops:

```bash
yokedcache ping                          # test connection
yokedcache stats                         # hit rate, key count, memory
yokedcache stats --watch                 # live refresh
yokedcache list --pattern "user:*"       # list matching keys
yokedcache search "alice" --threshold 80 # fuzzy search
yokedcache flush --tags "stale_data" --confirm
```

Set `YOKEDCACHE_REDIS_URL` and it'll pick up automatically. Run `yokedcache --help` for the full reference.

---

## Verify your install

```bash
# Check the version
python -c "import yokedcache; print(yokedcache.__version__)"

# If you have redis installed and a server running:
yokedcache ping
```

---

## What's next

- [Core Concepts](core-concepts.md) — how keys, TTL, tags, and serialization work
- [Backends](backends.md) — Memory, Redis, Memcached, Disk, SQLite, per-prefix routing
- [Usage Patterns](usage-patterns.md) — decorators, manual ops, invalidation, middleware, resilience
- [Configuration](configuration.md) — full config reference with all options
- [FastAPI Tutorial](tutorials/fastapi.md) — step-by-step complete app
- [Monitoring](monitoring.md) — Prometheus, StatsD, health checks
