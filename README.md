# YokedCache

High-Performance Caching for Modern Python Applications

[![PyPI version](https://img.shields.io/pypi/v/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![Python](https://img.shields.io/pypi/pyversions/yokedcache.svg)](https://pypi.org/project/yokedcache/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/sirstig/yokedcache/actions/workflows/test.yml/badge.svg)](https://github.com/sirstig/yokedcache/actions/workflows/test.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![PyPI - Downloads](https://img.shields.io/pypi/dm/yokedcache)

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
- **Zero-Code Integration**: Drop-in replacement for your existing database dependencies  
- **Intelligent Tagging**: Group and invalidate related caches effortlessly  
- **Fuzzy Search**: Find cached data with approximate matching  
- **Performance Insights**: Built-in metrics and monitoring tools

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

### Smart Invalidation

- Automatic cache invalidation on database writes
- Tag-based grouping for related data
- Pattern-based invalidation with wildcards
- Configurable rules per table/operation

### Deep Integration

- Zero-code FastAPI integration
- SQLAlchemy ORM support
- Async/await throughout
- Connection pooling & health checks

### Advanced Features

- Fuzzy search for approximate matches
- Multiple serialization methods
- Performance metrics & monitoring
- Variable TTLs with jitter

### Management Tools

- Comprehensive CLI for cache control
- Real-time statistics and monitoring
- YAML-based configuration
- Cache warming capabilities

## Installation

```bash
# Basic installation
pip install yokedcache

# With optional features
pip install yokedcache[sqlalchemy,fuzzy]  # Full-featured

# Development
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

# Test Redis connection
yokedcache ping

# List cached keys
yokedcache list --pattern "user:*"

# Flush specific caches
yokedcache flush --tags "user_data"

# Search cache contents
yokedcache search "alice" --threshold 80

# Monitor in real-time (JSON output for dashboards)
yokedcache stats --format json

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

```bash
# Install with dev dependencies
pip install yokedcache[dev]

# Run tests
pytest

# Run with coverage
pytest --cov=yokedcache

# Test specific functionality
pytest tests/test_cache.py::TestAutoInvalidation
```

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

## Acknowledgments

- [Redis](https://redis.io/) - For the excellent caching backend
- [FastAPI](https://fastapi.tiangolo.com/) - For the amazing Python web framework  
- [SQLAlchemy](https://www.sqlalchemy.org/) - For database ORM integration
- Python Community - For continuous inspiration and feedback

---

**Made with care by [Project Yoked LLC](https://github.com/sirstig)**

If YokedCache helps your project, please consider giving it a star on GitHub!
