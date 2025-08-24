# YokedCache

High-Performance Caching for Modern Python Applications

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

Intelligent caching with automatic invalidation, fuzzy search, and seamless FastAPI integration.

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

Traditional caching solutions require manual cache management and lack intelligent invalidation. YokedCache solves this with:

- **Smart Auto-Invalidation**: Automatically detects database changes and invalidates related caches
- **Multi-Backend Support**: Redis, Memcached, and in-memory backends for flexibility
- **Zero-Code Integration**: Drop-in replacement for your existing database dependencies  
- **Intelligent Tagging**: Group and invalidate related caches effortlessly  
- **Advanced Search**: Traditional fuzzy search plus vector-based semantic similarity
- **Production Monitoring**: Prometheus and StatsD integration for real-time metrics
- **Professional Tooling**: Comprehensive CLI with CSV export and monitoring capabilities

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

### 🔐 Production-Grade Resilience *(New in v0.2.1)*

- **Circuit Breaker Pattern**: Prevents cascading failures during Redis outages
- **Connection Pool Management**: Advanced Redis connection configuration
- **Retry Logic**: Exponential backoff for transient failures
- **Health Monitoring**: Comprehensive cache status and performance metrics
- **Graceful Fallbacks**: Application stability during cache issues

### 🔄 Enhanced Async/Sync Support *(New in v0.2.1)*

- **Smart Context Detection**: Prevents Task object returns in mixed environments
- **Explicit Method Variants**: `aget`/`aset` for async, `get_sync`/`set_sync` for sync
- **FastAPI Generator Support**: Better handling of database session dependencies
- **Performance Optimization**: Improved serialization and key generation

### Multi-Backend Architecture

- **Redis**: Full-featured backend with clustering and persistence support
- **Memcached**: High-performance distributed caching
- **In-Memory**: Fast local caching for development and testing
- Pluggable backend system for custom implementations

### Smart Invalidation

- Automatic cache invalidation on database writes
- Tag-based grouping for related data
- Pattern-based invalidation with wildcards
- Configurable rules per table/operation

### Advanced Search Capabilities

- Traditional fuzzy search with configurable thresholds
- Vector-based semantic similarity using TF-IDF and cosine similarity
- Multiple similarity algorithms (cosine, euclidean, manhattan)
- Redis vector persistence for large-scale deployments

### Deep Integration

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

### Advanced Usage

### Multi-Backend Configuration

```python
from yokedcache import YokedCache
from yokedcache.backends import RedisBackend, MemcachedBackend, MemoryBackend

# Redis backend (default)
redis_cache = YokedCache(backend=RedisBackend(
    redis_url="redis://localhost:6379/0"
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
