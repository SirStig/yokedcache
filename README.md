# yokedcache

[![PyPI version](https://img.shields.io/pypi/v/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![Python](https://img.shields.io/pypi/pyversions/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/sirstig/yokedcache/actions/workflows/test.yml/badge.svg)](https://github.com/sirstig/yokedcache/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/sirstig/yokedcache/branch/main/graph/badge.svg)](https://codecov.io/gh/sirstig/yokedcache)

Async-first Python caching for FastAPI and other asyncio services: Redis-oriented invalidation, pluggable backends, optional vector helpers, and metrics that fit real deployments.

**[Documentation](https://sirstig.github.io/yokedcache/)** · **[Changelog](https://sirstig.github.io/yokedcache/changelog.html)** · **[PyPI](https://pypi.org/project/yokedcache/)** · **[Issues](https://github.com/sirstig/yokedcache/issues)**

---

## Features

- **Invalidation** — Tags, patterns, and workflows that keep cache and writes aligned
- **FastAPI** — Dependency-friendly helpers (`cached_dependency`, decorators) without rewriting routes
- **Backends** — Redis (default), Memcached, memory, disk, SQLite; per-prefix routing
- **HTTP** — ETag / `Cache-Control` middleware and 304-friendly responses
- **Resilience** — Circuit breaker, retries, stale-if-error style patterns
- **Observability** — Prometheus, StatsD, OpenTelemetry hooks
- **CLI** — Inspect keys, stats, and health from the shell

## Installation

Current release line: **1.0.0-beta** (pre-release on PyPI).

```bash
pip install "yokedcache==1.0.0-beta"
```

For the latest pre-release without pinning:

```bash
pip install --pre yokedcache
```

Optional extras:

| Extra | Purpose |
|--------|---------|
| `memcached` | Memcached backend |
| `monitoring` | Prometheus / StatsD |
| `vector` | Vector / similarity helpers |
| `fuzzy` | Fuzzy matching utilities |
| `disk` | Disk backend |
| `sqlite` | SQLite backend |
| `tracing` | OpenTelemetry API/SDK |
| `full` | All of the above |
| `dev` | Tests, linters, type checking |

## Quick start

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

| | Minimum |
|---|---|
| Python | 3.9+ |
| Redis | 4.x client; server 6+ typical for production |

Other backends impose their own dependencies when you install the matching extra.

## Documentation

- [Getting started](https://sirstig.github.io/yokedcache/getting-started.html)
- [Usage patterns](https://sirstig.github.io/yokedcache/usage-patterns.html)
- [FastAPI tutorial](https://sirstig.github.io/yokedcache/tutorials/fastapi.html)
- [API reference (pdoc)](https://sirstig.github.io/yokedcache/api/)
- [llms.txt](https://sirstig.github.io/yokedcache/llms.txt) for tool-oriented summaries

## Security

Treat Redis and Memcached as **trusted** stores: anyone who can write arbitrary keys can affect deserialization. From **1.0.0-beta**, new values are written with a typed envelope; set `allow_legacy_insecure_deserialization=False` on `CacheConfig` once legacy entries are migrated. Do not use `HTTPCacheMiddleware` on authenticated routes without a `key_builder` that varies the key per user or session. See the changelog for details.

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
