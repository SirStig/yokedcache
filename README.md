# yokedcache

[![PyPI version](https://img.shields.io/pypi/v/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![Python](https://img.shields.io/pypi/pyversions/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/sirstig/yokedcache/actions/workflows/test.yml/badge.svg)](https://github.com/sirstig/yokedcache/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/sirstig/yokedcache/branch/main/graph/badge.svg)](https://codecov.io/gh/sirstig/yokedcache)

Async-first caching with the **same API** across backends: in-process memory (default install), Redis, Memcached, disk, and SQLite. Tag and pattern invalidation, optional Starlette HTTP middleware, and production metrics—use `await` in FastAPI, Starlette, Django async views, workers, or plain `asyncio`. **Sync code** is welcome too: `get_sync` / `set_sync` (and friends) or `@cached` on a normal `def`—same async-backed implementation, not a separate Redis client.

**[Documentation](https://sirstig.github.io/yokedcache/)** · **[Changelog](https://sirstig.github.io/yokedcache/changelog.html)** · **[PyPI](https://pypi.org/project/yokedcache/)** · **[Issues](https://github.com/sirstig/yokedcache/issues)**

---

## Features

- **Invalidation** — Tags, patterns, and workflows that keep cache and writes aligned
- **Backends** — Memory (no extra deps), Redis, Memcached, disk, SQLite; per-prefix routing
- **Framework-agnostic core** — async API in any asyncio context; sync helpers for scripts and blocking functions; FastAPI helpers optional
- **HTTP** — ETag / `Cache-Control` middleware (`yokedcache[web]` / Starlette)
- **Resilience** — Circuit breaker, retries, stale-if-error style patterns
- **Observability** — Prometheus, StatsD, OpenTelemetry (optional extras)
- **CLI** — Inspect keys, stats, and health from the shell

## Installation

```bash
pip install yokedcache
```

A plain install gives you the core package and an **in-process memory** cache when Redis is not configured (see [1.0.1 changelog](https://github.com/sirstig/yokedcache/blob/main/CHANGELOG.md)). If you previously relied on **transitive** `redis` or `fastapi` from yokedcache alone, add `pip install "yokedcache[redis]"`, `"yokedcache[web]"`, or `"yokedcache[full]"`, or declare those libraries in your own requirements.

Pin 1.x if your policy requires it:

```bash
pip install "yokedcache>=1.0.1"
```

### Preset extras

| Extra | What you get |
|--------|----------------|
| `redis` | `redis-py` for a real Redis server |
| `web` | Starlette (for `HTTPCacheMiddleware`) |
| `backends` | Disk + SQLite + Memcached client deps together |
| `observability` | Prometheus / StatsD + OpenTelemetry |
| `full` | Redis, FastAPI, all optional backends, monitoring, tracing, vector, fuzzy, SQLAlchemy |

### Individual extras

`memcached`, `disk`, `sqlite`, `monitoring`, `tracing`, `vector`, `fuzzy`, `sqlalchemy` — mix as needed, e.g. `pip install "yokedcache[redis,memcached]"`.

`dev` — tests, linters, type checking (for contributors).

## Quick start (memory, no Redis)

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

For Redis in production: `pip install "yokedcache[redis]"`, set `redis_url` (or env `YOKEDCACHE_REDIS_URL`), then `connect()` as usual.

### Sync code

Prefer `await` inside apps that already run an event loop. For scripts or blocking call stacks, connect once, then use `*_sync`:

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

## FastAPI example

Install FastAPI in your app (`pip install fastapi` or use `yokedcache[full]`).

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

| | Notes |
|---|---|
| Python | 3.10+ for **yokedcache 1.x** (CI: 3.10–3.14) |
| Redis | Optional; use `yokedcache[redis]` and a Redis 6+ server when you want a remote store |

**Python 3.9** is unsupported on 1.x. Pin **`yokedcache==0.3.0`** only as a temporary bridge; upgrade Python and yokedcache when you can.

## Documentation

- [Getting started](https://sirstig.github.io/yokedcache/getting-started.html)
- [Backends](https://sirstig.github.io/yokedcache/backends.html)
- [Usage patterns](https://sirstig.github.io/yokedcache/usage-patterns.html)
- [FastAPI tutorial](https://sirstig.github.io/yokedcache/tutorials/fastapi.html)
- [API reference (pdoc)](https://sirstig.github.io/yokedcache/api/)
- [llms.txt](https://sirstig.github.io/yokedcache/llms.txt)

## Security

Treat Redis and Memcached as **trusted** stores: anyone who can write arbitrary keys can affect deserialization. From **1.0.0**, new values are written with a typed envelope; set `allow_legacy_insecure_deserialization=False` on `CacheConfig` once legacy entries are migrated. Do not use `HTTPCacheMiddleware` on authenticated routes without a `key_builder` that varies the key per user or session. See the changelog for details.

**Optional `disk` extra:** installs **diskcache**, which uses **pickle** by default. **[CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)** (GHSA-w8v5-vhqr-4h9v) documents unsafe pickle deserialization when an attacker can write the cache directory; **there is no patched diskcache release on PyPI yet**, so dependency scanners may still alert. Use a non-world-writable cache path and skip `yokedcache[disk]` if you do not need disk persistence. Full write-up: **[SECURITY.md](SECURITY.md)** (also covers how we pin transitive deps in `uv.lock`).

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Build the static docs site locally:

```bash
pip install -e ".[docs]"
python scripts/build_docs_site.py
cp CHANGELOG.md site/changelog.md
python -m pdoc yokedcache -o site/api --template-directory site-src/pdoc-template
cd site && python -m http.server 8000
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow and review expectations.

## License

MIT. See [LICENSE](LICENSE).

Maintained by **Project Yoked LLC**; technical lead **Joshua Kac**.
