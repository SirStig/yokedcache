# YokedCache - Python Caching Library for FastAPI

High-Performance Redis Caching with Auto-Invalidation for Modern Python Applications

<div align="center">

[![⭐ Star YokedCache](https://img.shields.io/github/stars/sirstig/yokedcache?style=for-the-badge&logo=github&logoColor=white&color=yellow)](https://github.com/sirstig/yokedcache/stargazers)

[![PyPI version](https://img.shields.io/pypi/v/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![Python](https://img.shields.io/pypi/pyversions/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/sirstig/yokedcache/actions/workflows/test.yml/badge.svg)](https://github.com/sirstig/yokedcache/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/sirstig/yokedcache/branch/main/graph/badge.svg)](https://codecov.io/gh/sirstig/yokedcache)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![PyPI - Downloads](https://img.shields.io/pypi/dm/yokedcache)

</div>

Intelligent Python caching library with automatic Redis invalidation, vector search caching, and seamless FastAPI integration.

**[Documentation](https://sirstig.github.io/yokedcache)** | **[Report Bug](https://github.com/sirstig/yokedcache/issues)** | **[Request Feature](https://github.com/sirstig/yokedcache/issues)**

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Usage Examples](#usage-examples)
- [CLI Usage](#cli-usage)
- [Performance](#performance)
- [Architecture](#architecture)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Traditional Python caching solutions require manual cache management and lack intelligent invalidation. YokedCache is the premier Python caching library for FastAPI applications, solving this with:

- **Smart Auto-Invalidation**: Automatically detects database changes and invalidates related Redis caches
- **Multi-Backend Support**: Redis caching, Memcached, and in-memory backends for flexible deployment
- **Zero-Code FastAPI Integration**: Drop-in replacement for your existing FastAPI database dependencies
- **Intelligent Redis Tagging**: Group and invalidate related cache entries effortlessly
- **Advanced Vector Search**: Traditional fuzzy search plus vector-based semantic similarity caching
- **Production Monitoring**: Prometheus and StatsD integration for real-time Redis cache metrics
- **Professional Tooling**: Comprehensive CLI with CSV export and Redis cache monitoring capabilities

## Quick Start

```bash
pip install yokedcache
```

```python
from fastapi import FastAPI, Depends
from yokedcache import cached_dependency

app = FastAPI()

# Replace your database dependency
cached_get_db = cached_dependency(get_db, ttl=300)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    # Your existing code - no changes needed!
    return db.query(User).filter(User.id == user_id).first()
```

That's it! Your database queries are now cached with automatic invalidation.

## Key Features

### � Advanced Caching Patterns *(New in v0.3.0)*

- **HTTP Response Middleware**: ETag/Cache-Control headers with 304 Not Modified responses
- **Single-Flight Protection**: Prevents cache stampede with automatic deduplication
- **Stale-While-Revalidate**: Serve stale data while refreshing in background
- **Stale-If-Error**: Fallback to cached data during service failures
- **Per-Prefix Routing**: Shard cache keys across multiple backends by prefix
- **OpenTelemetry Integration**: Distributed tracing with spans and metrics

### �🔐 Production-Grade Resilience for Python FastAPI Apps *(New in v0.2.1)*

- **Circuit Breaker Pattern**: Prevents cascading failures during Redis cache outages
- **Redis Connection Pool Management**: Advanced Redis caching configuration
- **Retry Logic**: Exponential backoff for transient Redis cache failures
- **Health Monitoring**: Comprehensive Redis cache status and performance metrics
- **Graceful Fallbacks**: FastAPI application stability during cache issues

### 🔄 Enhanced Python Async/Sync Support *(New in v0.2.1)*

- **Smart Context Detection**: Prevents Task object returns in mixed Python environments
- **Explicit Method Variants**: `aget`/`aset` for async, `get_sync`/`set_sync` for sync Redis operations
- **FastAPI Generator Support**: Better handling of database session dependencies
- **Performance Optimization**: Improved serialization and Redis cache key generation

### Multi-Backend Redis Caching Architecture

- **Redis**: Full-featured backend with clustering and persistence support for production caching
- **Memcached**: High-performance distributed caching
- **DiskCache**: Local disk-based persistent caching
- **SQLite**: Embedded database caching with TTL support
- **In-Memory**: Fast local Python caching for development and testing
- Pluggable backend system for custom Redis cache implementations

### Smart Redis Cache Invalidation

- Automatic cache invalidation on database writes
- Tag-based grouping for related data
- Pattern-based invalidation with wildcards
- Configurable rules per table/operation

### Advanced Vector Search Caching Capabilities

- Traditional fuzzy search with configurable thresholds
- Vector-based semantic similarity caching using TF-IDF and cosine similarity
- Multiple similarity algorithms (cosine, euclidean, manhattan)
- Redis vector persistence for large-scale deployments

### Deep FastAPI and Python Integration

- Zero-code FastAPI integration
- SQLAlchemy ORM support
- Async/await throughout
- Connection pooling & health checks

### Production Monitoring

- **Prometheus**: Native metrics export for Grafana dashboards
- **StatsD**: Real-time metrics for DataDog, Grafana, and other platforms
- Comprehensive performance tracking and alerting
- Custom metrics collection support

### Professional Tooling

- Comprehensive CLI for cache control and monitoring
- CSV export for data analysis and reporting
- Real-time statistics with watch mode
- YAML-based configuration with validation
- Cache warming and bulk operations

## Installation

```bash
# Basic installation (Redis backend only)
pip install yokedcache

# With specific features
pip install yokedcache[memcached]     # Add Memcached support
pip install yokedcache[monitoring]    # Add Prometheus/StatsD support
pip install yokedcache[vector]        # Add vector similarity search
pip install yokedcache[fuzzy]         # Add traditional fuzzy search
pip install yokedcache[disk]          # Add disk-based backend
pip install yokedcache[tracing]       # Add OpenTelemetry tracing

# Full installation with all features
pip install yokedcache[full]

# Development installation
pip install yokedcache[dev]
```

## Documentation

| Guide | Link | Description |
|-------|------|-------------|
| Quick Start | [Getting Started](#quick-start) | 5-minute integration guide |
| API Reference | [Documentation](https://sirstig.github.io/yokedcache) | Complete API documentation |
| Examples | [Examples](examples/) | Real-world usage examples |
| CLI Guide | [CLI Usage](#cli-usage) | Command-line tool documentation |

## Usage Examples

### Enhanced Configuration *(New in v0.2.1)*

```python
from yokedcache import YokedCache, CacheConfig

# Production-ready configuration with resilience features
config = CacheConfig(
    redis_url="redis://localhost:6379",
    max_connections=50,

    # Circuit breaker for Redis failures
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_timeout=60.0,

    # Enhanced connection pool settings
    connection_pool_kwargs={
        "socket_connect_timeout": 5.0,
        "socket_timeout": 5.0,
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30
    },

    # Error handling and fallbacks
    fallback_enabled=True,
    connection_retries=3,
    retry_delay=0.1
)

cache = YokedCache(config=config)

# Monitor cache health
health = await cache.detailed_health_check()
print(f"Cache status: {health['status']}")
print(f"Connection pool: {health['connection_pool']}")

# Get comprehensive metrics
metrics = cache.get_comprehensive_metrics()
print(f"Hit rate: {metrics.hit_rate:.2%}")
print(f"Average response time: {metrics.avg_response_time:.3f}s")
```

### Explicit Async/Sync Methods *(New in v0.2.1)*

```python
# Explicit async methods (recommended in async contexts)
value = await cache.aget("user:123")
await cache.aset("user:123", user_data, ttl=300)
exists = await cache.aexists("user:123")
await cache.adelete("user:123")

# Explicit sync methods (for sync contexts)
value = cache.get_sync("user:123")
cache.set_sync("user:123", user_data, ttl=300)
exists = cache.exists_sync("user:123")
cache.delete_sync("user:123")

# Smart context-aware methods (auto-detect async/sync)
value = await cache.get("user:123")  # In async context
value = cache.get("user:123")        # In sync context
```

```python
from fastapi import FastAPI, Depends
from yokedcache import YokedCache, cached_dependency

app = FastAPI()
cache = YokedCache(redis_url="redis://localhost:6379/0")

# Wrap your existing database dependency
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    # Your existing code works unchanged!
    return db.query(User).filter(User.id == user_id).first()

# Automatic caching + invalidation now active!
```

### Advanced Caching Patterns *(New in v0.3.0)*

#### HTTP Response Middleware

```python
from fastapi import FastAPI
from yokedcache.middleware import CacheMiddleware

app = FastAPI()

# Add HTTP caching middleware
app.add_middleware(
    CacheMiddleware,
    cache_ttl=300,
    cache_key_prefix="http",
    include_paths=["/api/*"],
    exclude_paths=["/admin/*"]
)

@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    # Response automatically cached with ETag headers
    # Returns 304 Not Modified for unchanged data
    return {"id": user_id, "name": "John Doe"}
```

#### Single-Flight Protection & Stale-While-Revalidate

```python
from yokedcache import YokedCache, CacheConfig

config = CacheConfig(
    redis_url="redis://localhost:6379",
    enable_stale_while_revalidate=True,
    enable_stale_if_error=True
)
cache = YokedCache(config)

# Single-flight protection prevents stampede
async def expensive_operation(key: str):
    # Only one instance of this will run per key
    # Other requests wait for the result
    return await cache.fetch_or_set(
        key,
        fetcher_func=lambda: compute_expensive_data(),
        ttl=300
    )

# Stale-while-revalidate: serve stale data while refreshing
@cache.cached(ttl=60, stale_while_revalidate=True)
async def get_user_data(user_id: int):
    # Returns cached data immediately if stale
    # Triggers background refresh for next request
    return fetch_user_from_db(user_id)
```

#### Per-Prefix Backend Routing

```python
from yokedcache import YokedCache
from yokedcache.backends import DiskCacheBackend, RedisBackend

cache = YokedCache()

# Setup prefix-based routing
cache.setup_prefix_routing()

# Route different data types to different backends
cache.add_backend_route("user:", RedisBackend("redis://localhost:6379/0"))
cache.add_backend_route("temp:", DiskCacheBackend("/tmp/cache"))
cache.add_backend_route("session:", RedisBackend("redis://localhost:6379/1"))

# Data automatically routed based on key prefix
await cache.set("user:123", user_data)      # -> Redis DB 0
await cache.set("temp:abc", temp_data)      # -> Disk cache
await cache.set("session:xyz", session)    # -> Redis DB 1
```

#### OpenTelemetry Distributed Tracing

```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.tracing import initialize_tracing

# Initialize global tracing
initialize_tracing(
    service_name="my-api",
    enabled=True,
    sample_rate=1.0
)

config = CacheConfig(
    redis_url="redis://localhost:6379",
    enable_tracing=True
)
cache = YokedCache(config)

# All cache operations automatically traced
async with cache.tracer.trace_operation("get_user", "user:123"):
    user = await cache.get("user:123")
    # Span includes timing, hit/miss, backend info
```

### Advanced Usage

### Multi-Backend Configuration

```python
from yokedcache import YokedCache
from yokedcache.backends import RedisBackend, MemcachedBackend, MemoryBackend, DiskCacheBackend

# Redis backend (default)
redis_cache = YokedCache(backend=RedisBackend(
    redis_url="redis://localhost:6379/0"
))

# Disk-based persistent cache
disk_cache = YokedCache(backend=DiskCacheBackend(
    directory="/var/cache/myapp"
))

# Memcached backend
memcached_cache = YokedCache(backend=MemcachedBackend(
    servers=["localhost:11211"]
))

# In-memory backend for development
memory_cache = YokedCache(backend=MemoryBackend(
    max_size=1000  # Limit to 1000 keys
))
```

### Vector-Based Similarity Search

```python
from yokedcache.vector_search import VectorSimilaritySearch

# Initialize vector search
vector_search = VectorSimilaritySearch(
    similarity_method="cosine",  # or "euclidean", "manhattan"
    max_features=1000
)

# Perform semantic search
results = await cache.vector_search(
    query="user authentication",
    threshold=0.5,  # 50% similarity
    max_results=10
)
```

### Production Monitoring

```python
from yokedcache.monitoring import PrometheusCollector, StatsDCollector, CacheMetrics

# Set up Prometheus monitoring
prometheus = PrometheusCollector(namespace="myapp")
cache_metrics = CacheMetrics([prometheus])

# Set up StatsD monitoring
statsd = StatsDCollector(host="statsd.example.com", prefix="myapp.cache")
cache_metrics.add_collector(statsd)

# Initialize cache with monitoring
cache = YokedCache(metrics=cache_metrics)
```

### Configuration with YAML

```yaml
# cache_config.yaml
default_ttl: 300
key_prefix: "myapp"

tables:
  users:
    ttl: 3600  # 1 hour for user data
    tags: ["user_data"]
    invalidate_on: ["insert", "update", "delete"]
```

### Manual Cache Control

```python
from yokedcache import YokedCache, cached

cache = YokedCache()

# Decorator caching
@cached(cache=cache, ttl=600, tags=["products"])
async def get_expensive_data(query: str):
    return expensive_db_query(query)

# Manual operations
await cache.set("key", {"data": "value"}, ttl=300, tags=["api"])
data = await cache.get("key")
await cache.invalidate_tags(["products"])
```

## CLI Usage

YokedCache includes a powerful CLI for cache management:

```bash
# View cache statistics
yokedcache stats --watch

# Export stats to CSV for analysis
yokedcache stats --format csv --output cache_stats.csv

# Export stats to JSON for dashboards
yokedcache stats --format json --output stats.json

# Test connection to different backends
yokedcache ping --backend redis
yokedcache ping --backend memcached

# List cached keys with filtering
yokedcache list --pattern "user:*" --limit 50

# Flush specific caches by tags
yokedcache flush --tags "user_data,session_data"

# Advanced search with vector similarity
yokedcache search "user authentication" --method vector --threshold 0.5

# Traditional fuzzy search
yokedcache search "alice" --method fuzzy --threshold 80

# Monitor in real-time with CSV logging
yokedcache stats --format csv --output metrics.csv --watch

# Export current configuration
yokedcache export-config --output config.yaml

# Warm cache with predefined data
yokedcache warm --config-file cache_config.yaml
```

## Performance

| Metric | Improvement | Description |
|--------|-------------|-------------|
| Database Load | 60-90% reduction | Automatic query caching |
| Response Time | 200-500ms faster | Redis-fast cache hits |
| Memory Usage | Optimized | Efficient serialization |
| Setup Time | Under 5 minutes | Drop-in integration |

## Architecture

```mermaid
graph TB
    A[FastAPI App] --> B[YokedCache Wrapper]
    B --> C{Cache Hit?}
    C -->|Yes| D[Return Cached Data]
    C -->|No| E[Query Database]
    E --> F[Store in Redis]
    F --> G[Return Data]
    H[Database Write] --> I[Auto-Invalidation]
    I --> J[Clear Related Cache]
```

## Testing

YokedCache includes comprehensive test coverage for all features:

### Quick Verification

```bash
# Verify all features are working
python test_quick_verification.py
```

### Full Test Suite

```bash
# Install development dependencies
pip install yokedcache[dev]

# Run all tests
pytest

# Run with coverage
pytest --cov=yokedcache --cov-report=html

# Run specific feature tests
pytest tests/test_backends.py      # Multi-backend tests
pytest tests/test_vector_search.py # Vector similarity tests
pytest tests/test_monitoring.py    # Monitoring tests
pytest tests/test_cli.py           # CLI tests
```

### Test Categories

- **Backend Tests**: Memory, Redis, Memcached implementations
- **Vector Search Tests**: TF-IDF, cosine similarity, semantic search
- **Monitoring Tests**: Prometheus, StatsD, metrics collection
- **CLI Tests**: CSV export, search commands, configuration
- **Integration Tests**: End-to-end workflows and error handling

For detailed testing information, see the [Testing Guide](docs/testing.md).

## Contributing

We welcome contributions! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit your changes: `git commit -m "feat: add amazing feature"`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Project Status

[![GitHub stars](https://img.shields.io/github/stars/sirstig/yokedcache?style=social)](https://github.com/sirstig/yokedcache/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/sirstig/yokedcache?style=social)](https://github.com/sirstig/yokedcache/network/members)
[![GitHub issues](https://img.shields.io/github/issues/sirstig/yokedcache)](https://github.com/sirstig/yokedcache/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/sirstig/yokedcache)](https://github.com/sirstig/yokedcache/pulls)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with care by [Project Yoked LLC](https://github.com/sirstig)**
