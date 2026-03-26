# Testing

How to test code that uses YokedCache—both the library's own test suite and your application's tests.

---

## Testing your application

### Use the memory backend

The memory backend requires no external services and is the easiest choice for unit and integration tests:

```python
import pytest
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

@pytest.fixture
async def cache():
    c = YokedCache(CacheConfig())  # memory backend
    await c.connect()
    yield c
    await c.disconnect()
```

### Basic async test

```python
import pytest

@pytest.mark.asyncio
async def test_set_and_get(cache):
    await cache.set("key", "value", ttl=60)
    result = await cache.get("key")
    assert result == "value"

@pytest.mark.asyncio
async def test_expiry(cache):
    await cache.set("key", "value", ttl=1)
    import asyncio
    await asyncio.sleep(1.1)
    assert await cache.get("key") is None

@pytest.mark.asyncio
async def test_tag_invalidation(cache):
    await cache.set("user:1", {"name": "Alice"}, tags=["users"])
    await cache.set("user:2", {"name": "Bob"}, tags=["users"])
    await cache.invalidate_tags(["users"])
    assert await cache.get("user:1") is None
    assert await cache.get("user:2") is None
```

### Testing `@cached` functions

```python
@cached(cache=cache, ttl=300)
async def get_user(user_id: int):
    return await db.fetch_user(user_id)

@pytest.mark.asyncio
async def test_cached_function(cache, mocker):
    mock_fetch = mocker.patch("mymodule.db.fetch_user", return_value={"name": "Alice"})

    # First call — hits the DB
    result1 = await get_user(42)
    assert mock_fetch.call_count == 1

    # Second call — from cache
    result2 = await get_user(42)
    assert mock_fetch.call_count == 1   # not called again

    assert result1 == result2
```

### Testing cache invalidation

```python
@pytest.mark.asyncio
async def test_invalidation_after_write(cache, test_client):
    # Warm the cache
    response = test_client.get("/users/1")
    assert response.json()["name"] == "Alice"

    # Write update
    test_client.put("/users/1", json={"name": "Alicia"})

    # Cache should be invalidated — next read is fresh
    response = test_client.get("/users/1")
    assert response.json()["name"] == "Alicia"
```

### Testing that caching works (hit/miss counts)

```python
@pytest.mark.asyncio
async def test_cache_is_used(cache, mocker):
    db_call = mocker.patch("mymodule.db.fetch_user", return_value={"id": 1})

    for _ in range(5):
        await get_user(1)

    # DB should only be called once despite 5 requests
    assert db_call.call_count == 1

    stats = await cache.get_stats()
    assert stats.cache_hits == 4
    assert stats.cache_misses == 1
```

---

## Using fakeredis for Redis-backed tests

If you need to test Redis-specific behavior without a real server, use `fakeredis`:

```bash
pip install fakeredis
```

```python
import fakeredis.aioredis
import pytest
from unittest.mock import patch

@pytest.fixture
async def redis_cache():
    with patch("redis.asyncio.Redis", fakeredis.aioredis.FakeRedis):
        from yokedcache import YokedCache
        from yokedcache.config import CacheConfig
        c = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))
        await c.connect()
        yield c
        await c.disconnect()
```

---

## FastAPI test client

```python
import pytest
from fastapi.testclient import TestClient
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

from myapp import app, cache as app_cache

@pytest.fixture
def client():
    # Override the app's cache with an in-memory one
    test_cache = YokedCache(CacheConfig())

    # If your app uses a module-level cache, patch it
    import myapp
    original = myapp.cache
    myapp.cache = test_cache

    with TestClient(app) as c:
        import asyncio
        asyncio.run(test_cache.connect())
        yield c
        asyncio.run(test_cache.disconnect())

    myapp.cache = original  # restore

def test_get_user(client):
    response = client.get("/users/1")
    assert response.status_code == 200

def test_cache_invalidation(client):
    # Read
    r1 = client.get("/users/1")
    assert r1.status_code == 200

    # Write (should invalidate)
    client.put("/users/1", json={"name": "New Name"})

    # Re-read
    r2 = client.get("/users/1")
    assert r2.json()["name"] == "New Name"
```

---

## pytest-asyncio setup

YokedCache's tests use `pytest-asyncio` in auto mode. Add this to `pytest.ini` or `pyproject.toml`:

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## Skipping tests for optional dependencies

Use `pytest.importorskip` at the top of test modules:

```python
# test_vector_search.py
pytest.importorskip("numpy")   # skip entire module if numpy isn't installed
pytest.importorskip("sklearn")

from yokedcache.vector_search import VectorSimilaritySearch

def test_vector_search():
    ...
```

Or per test:

```python
@pytest.mark.skipif(
    not importlib.util.find_spec("prometheus_client"),
    reason="prometheus_client not installed"
)
def test_prometheus_collector():
    ...
```

---

## Running the library's own tests

```bash
# Setup
pip install -e ".[dev]"

# All tests
pytest

# With coverage
pytest --cov=yokedcache --cov-report=html
open htmlcov/index.html

# Stop on first failure
pytest -x

# Verbose
pytest -v

# Specific module
pytest tests/test_backends.py

# Specific class
pytest tests/test_backends.py::TestRedisBackend

# Specific test
pytest tests/test_backends.py::TestRedisBackend::test_basic_set_get

# Skip slow tests
pytest -m "not slow"

# Parallel (requires pytest-xdist)
pytest -n auto
```

### With Redis

Start a Redis server before running Redis-dependent tests:

```bash
docker run -d --name test-redis -p 6379:6379 redis:7-alpine
pytest tests/test_backends.py::TestRedisBackend
```

### With Memcached

```bash
docker run -d --name test-memcached -p 11211:11211 memcached:alpine
pytest tests/test_backends.py::TestMemcachedBackend
```

---

## Test structure

```
tests/
├── conftest.py              # shared fixtures (cache instances, DB sessions)
├── test_cache.py            # core YokedCache operations
├── test_backends.py         # per-backend tests (memory, Redis, Memcached)
├── test_decorators.py       # @cached and cached_dependency
├── test_invalidation.py     # tag, pattern, and auto-invalidation
├── test_vector_search.py    # vector similarity search
├── test_monitoring.py       # health checks and metrics collectors
├── test_middleware.py       # HTTP cache middleware
└── test_cli.py              # CLI commands via Click test runner
```

### Testing CLI commands

```python
from click.testing import CliRunner
from yokedcache.cli import cli

def test_ping():
    runner = CliRunner()
    result = runner.invoke(cli, ["ping"])
    assert result.exit_code == 0
    assert "OK" in result.output

def test_stats():
    runner = CliRunner()
    result = runner.invoke(cli, ["stats", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "hit_rate" in data
```

---

## CI

The project runs tests on Python 3.10–3.14, across Linux, macOS, and Windows. Optional-dependency tests are conditional on those extras being installed.

Pre-commit hooks run Black, isort, flake8, and mypy before every commit:

```bash
pre-commit install
pre-commit run --all-files  # run manually
```
