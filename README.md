# YokedCache

[![PyPI version](https://badge.fury.io/py/yokedcache.svg)](https://badge.fury.io/py/yokedcache)
[![Python Support](https://img.shields.io/pypi/pyversions/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/sirstig/yokedcache/workflows/Tests/badge.svg)](https://github.com/sirstig/yokedcache/actions)

A robust, performance-focused caching library for Python backends, specifically tailored for FastAPI applications integrated with databases and Redis as the cache backend.

## 🚀 Problem Statement

Tired of manual caching in FastAPI? YokedCache automates it with Redis smarts.

Traditional caching solutions require manual cache key management, lack database integration, and don't handle cache invalidation intelligently. YokedCache provides a "plug-and-play" system that wraps your database dependencies to automatically handle caching with minimal code changes.

## ✨ Key Features

- **🔄 Auto-Invalidation**: Automatically invalidates caches when database writes occur
- **🎯 Deep Database Integration**: Seamlessly wraps SQLAlchemy and other ORMs
- **🔍 Fuzzy Search**: Built-in fuzzy searching for approximate cache matches
- **⚡ Variable TTLs**: Fine-grained control over cache expiration times
- **🏷️ Tag-Based Invalidation**: Group and invalidate related caches efficiently
- **🖥️ CLI Management**: Command-line tools for monitoring and cache control
- **📊 Performance Metrics**: Built-in hit/miss ratio tracking
- **🔧 Easy Integration**: Swap your DB dependency with minimal code changes

## 📦 Installation

### Option 1: Modern approach (Recommended)
```bash
# Basic installation
pip install yokedcache

# With SQLAlchemy support
pip install yokedcache[sqlalchemy]

# With fuzzy search capabilities
pip install yokedcache[fuzzy]

# Full installation with all optional dependencies
pip install yokedcache[sqlalchemy,fuzzy]

# Development installation
pip install yokedcache[dev]
```

### Option 2: Requirements files
```bash
# Minimal core functionality
pip install -r requirements-minimal.txt

# All features included
pip install -r requirements-full.txt

# Development environment
pip install -r requirements-dev.txt
```

## 🚀 Quick Start

### 1. Basic FastAPI Integration

```python
from fastapi import FastAPI, Depends
from yokedcache import YokedCache, cached_dependency
import sqlalchemy as sa

app = FastAPI()

# Initialize YokedCache
cache = YokedCache(
    redis_url="redis://localhost:6379/0",
    config_file="cache_config.yaml"  # Optional
)

# Your existing database dependency
def get_db():
    # Your database session logic here
    pass

# Wrap with caching - that's it!
cached_get_db = cached_dependency(get_db, cache=cache)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    # Your existing code - no changes needed!
    user = db.query(User).filter(User.id == user_id).first()
    return user
```

### 2. Configuration File (cache_config.yaml)

```yaml
# Default settings
default_ttl: 300  # 5 minutes
key_prefix: "myapp"

# Per-table cache settings
tables:
  users:
    ttl: 3600  # 1 hour for user data
    tags: ["user_data"]
    invalidate_on: ["insert", "update", "delete"]
  
  posts:
    ttl: 1800  # 30 minutes for posts
    tags: ["content"]
    invalidate_on: ["insert", "update", "delete"]

# Fuzzy search settings
fuzzy:
  enabled: true
  threshold: 80
  max_results: 10
```

### 3. Advanced Usage with Manual Control

```python
from yokedcache import YokedCache

cache = YokedCache(redis_url="redis://localhost:6379/0")

# Manual caching
@cache.cached(ttl=600, tags=["products"])
async def get_expensive_data(query: str):
    # Expensive database operation
    return expensive_db_query(query)

# Fuzzy search
results = await cache.fuzzy_search("approximate query", threshold=85)

# Manual invalidation
await cache.invalidate_tags(["products"])
await cache.invalidate_pattern("user:*")
```

## 🖥️ CLI Usage

YokedCache comes with a powerful CLI for cache management:

```bash
# View cache statistics
yokedcache stats

# List cached keys
yokedcache list --prefix "myapp:users"

# Flush specific caches
yokedcache flush --pattern "user:*"
yokedcache flush --tags "user_data,content"

# Warm cache with predefined queries
yokedcache warm --config cache_config.yaml

# Monitor in real-time (JSON output for dashboards)
yokedcache stats --format json --watch
```

## 🏗️ Architecture

YokedCache is built around several core concepts:

- **Cache Wrapper**: Transparently wraps your database dependencies
- **Smart Keys**: Auto-generates cache keys from query patterns and parameters
- **Tag System**: Groups related caches for efficient batch invalidation
- **Write Detection**: Monitors database writes to trigger automatic invalidation
- **Fuzzy Matching**: Enables approximate searches across cached data

## 🔧 Advanced Configuration

### Environment Variables

```bash
YOKEDCACHE_REDIS_URL=redis://localhost:6379/0
YOKEDCACHE_DEFAULT_TTL=300
YOKEDCACHE_KEY_PREFIX=myapp
YOKEDCACHE_LOG_LEVEL=INFO
```

### Programmatic Configuration

```python
from yokedcache import YokedCache, CacheConfig

config = CacheConfig(
    redis_url="redis://localhost:6379/0",
    default_ttl=300,
    key_prefix="myapp",
    enable_fuzzy=True,
    fuzzy_threshold=80
)

cache = YokedCache(config=config)
```

## 🧪 Testing

YokedCache includes testing utilities:

```python
from yokedcache.testing import MockYokedCache

# Use in tests
def test_my_function():
    cache = MockYokedCache()
    # Your test code here
```

## 📊 Performance

YokedCache is designed for high-performance applications:

- **Async/Await Support**: Full async compatibility with FastAPI
- **Connection Pooling**: Efficient Redis connection management
- **Minimal Overhead**: Lightweight wrapper with negligible performance impact
- **Smart Serialization**: Efficient data serialization for Redis storage

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the need for better caching in FastAPI applications
- Built on top of excellent libraries: Redis, FastAPI, SQLAlchemy
- Thanks to the Python community for feedback and contributions

## 📚 Documentation

For detailed documentation, examples, and API reference, visit our [documentation site](https://sirstig.github.io/yokedcache).

## 🐛 Support

- **Issues**: [GitHub Issues](https://github.com/sirstig/yokedcache/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sirstig/yokedcache/discussions)
- **Security**: Please report security issues privately by creating a private issue
