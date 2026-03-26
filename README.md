# yokedcache

[![PyPI version](https://img.shields.io/pypi/v/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![Python](https://img.shields.io/pypi/pyversions/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/sirstig/yokedcache/actions/workflows/test.yml/badge.svg)](https://github.com/sirstig/yokedcache/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/sirstig/yokedcache/branch/main/graph/badge.svg)](https://codecov.io/gh/sirstig/yokedcache)

Async-first caching with the same API across backends: in-process memory (works out of the box), Redis, Memcached, disk, and SQLite. Tag and pattern invalidation, optional HTTP middleware, and production metrics built in.

Use `await` in FastAPI, Django async views, workers, or plain asyncio. Sync code is welcome too—`get_sync` / `set_sync` / `@cached` on a normal `def` run the same async implementation, no separate client needed.

**[Documentation](https://sirstig.github.io/yokedcache/)** · **[Changelog](https://sirstig.github.io/yokedcache/changelog.html)** · **[PyPI](https://pypi.org/project/yokedcache/)** · **[Issues](https://github.com/sirstig/yokedcache/issues)**

---

## What's included

- **Multiple backends** — Memory (zero deps), Redis, Memcached, disk, SQLite; per-prefix routing to mix them
- **Invalidation** — Tag-based, pattern-based, and auto-invalidation on DB writes
- **Sync + async** — Full async API; sync helpers for scripts and blocking code
- **HTTP middleware** — ETag / `Cache-Control` via Starlette (`yokedcache[web]`)
- **Resilience** — Circuit breaker, retries, stale-if-error
- **Observability** — Prometheus, StatsD, OpenTelemetry (optional extras)
- **CLI** — Inspect keys, stats, and run health checks from the shell

## Installation

```bash
pip install yokedcache
```

The base install ships with an in-process memory backend—no Redis required to get started. Add extras when you need them:

| Extra | What it adds |
|-------|-------------|
| `redis` | Redis backend via `redis-py` |
| `web` | Starlette HTTP cache middleware |
| `backends` | Disk, SQLite, and Memcached deps together |
| `observability` | Prometheus, StatsD, OpenTelemetry |
| `full` | Everything above plus fuzzy search, vector search, SQLAlchemy helpers |

Individual extras: `memcached`, `disk`, `sqlite`, `monitoring`, `tracing`, `vector`, `fuzzy`, `sqlalchemy`.

## Quick start

**Async (memory backend, no Redis needed):**

```python
import asyncio
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

async def main():
    cache = YokedCache(CacheConfig())
    await cache.connect()
    await cache.set("user:1", {"name": "Ada"}, ttl=60)
    print(await cache.get("user:1"))
    await cache.disconnect()

asyncio.run(main())
```

**Sync (scripts and blocking code):**

```python
import asyncio
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig())
asyncio.run(cache.connect())
cache.set_sync("user:1", {"name": "Ada"}, ttl=60)
print(cache.get_sync("user:1"))
asyncio.run(cache.disconnect())
```

For Redis: `pip install "yokedcache[redis]"`, then set `redis_url="redis://..."` on `CacheConfig` (or the env var `YOKEDCACHE_REDIS_URL`).

## FastAPI example

```python
from fastapi import FastAPI, Depends
from yokedcache import cached_dependency

app = FastAPI()

cached_get_db = cached_dependency(get_db, ttl=300)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    return db.query(User).filter(User.id == user_id).first()
```

## Requirements

- **Python 3.10+** (tested on 3.10–3.14)
- **Redis** is optional; install `yokedcache[redis]` and point to a Redis 6+ server when you want a shared remote cache

Python 3.9 is not supported on 1.x. Pin `yokedcache==0.3.0` only as a temporary bridge—it does not receive security fixes. Upgrade when you can.

## Security

Treat Redis and Memcached as trusted stores—anyone who can write arbitrary keys can affect what your app deserializes. Set `allow_legacy_insecure_deserialization=False` on `CacheConfig` once you've migrated away from legacy entries.

The optional `disk` extra pulls in `diskcache`, which uses pickle. **[CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)** covers unsafe deserialization if an attacker can write to the cache directory—no patched PyPI release exists yet. Skip the `disk` extra if you don't need it; keep the cache directory non-world-writable if you do. See [SECURITY.md](SECURITY.md).

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Build the docs site locally:

```bash
pip install -e ".[docs]"
python scripts/build_docs_site.py
cp CHANGELOG.md site/changelog.md
python -m pdoc yokedcache -o site/api --template-directory site-src/pdoc-template
cd site && python -m http.server 8000
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

MIT. See [LICENSE](LICENSE).

Maintained by **Project Yoked LLC**; technical lead **Joshua Kac**.
