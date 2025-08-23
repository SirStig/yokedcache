---
title: YokedCache Documentation
---

# YokedCache

**High-Performance Caching for Modern Python Applications**

YokedCache is a powerful, async-first caching library that brings enterprise-grade caching capabilities to Python applications. With multi-backend support, intelligent invalidation, and production-ready monitoring, it's designed to scale from development to enterprise deployment.

## Why YokedCache?

- **🚀 Performance**: Async-first design with connection pooling and batch operations
- **🔧 Flexible**: Multiple backends (Memory, Redis, Memcached) with unified API
- **🧠 Intelligent**: Auto-invalidation, vector search, and fuzzy matching
- **📊 Observable**: Built-in metrics, monitoring, and comprehensive CLI tools
- **🛡️ Production-Ready**: Health checks, error handling, and security features

## Quick Start

```bash
# Install with all features
pip install yokedcache[full]
```

```python
from fastapi import FastAPI, Depends
from yokedcache import YokedCache, cached_dependency

app = FastAPI()
cache = YokedCache()  # Uses Redis by default

# Cache database dependencies automatically
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    # Database queries are automatically cached and invalidated
    return db.query(User).filter(User.id == user_id).first()
```

## Documentation Guide

### 📚 **Start Here**
Perfect for newcomers and quick setups:

- **[Getting Started](getting-started.md)** - Installation, first setup, and basic usage
- **[Core Concepts](core-concepts.md)** - Keys, TTL, tags, serialization, and architecture
- **[Configuration Guide](configuration.md)** - Complete configuration reference and best practices

### 🏗️ **Architecture & Backends**
Choose and configure your caching infrastructure:

- **[Backend Overview](backends.md)** - Memory, Redis, and Memcached backends
- **[Redis Setup](redis-setup.md)** - Redis installation and configuration guide

### 💻 **Usage Patterns**
Learn different ways to use YokedCache:

- **[Usage Patterns](usage-patterns.md)** - Function caching, auto-invalidation, and fuzzy search
- **[FastAPI Integration](tutorials/fastapi.md)** - Complete FastAPI tutorial with examples
- **[SQLAlchemy Integration](tutorials/sqlalchemy.md)** - Database ORM integration patterns

### 🔍 **Advanced Features**
Powerful capabilities for complex use cases:

- **[Vector Search](vector-search.md)** - Semantic similarity search capabilities
- **[Production Monitoring](monitoring.md)** - Metrics, health checks, and observability

### 🛠️ **Tools & CLI**
Command-line tools and utilities:

- **[CLI Reference](cli.md)** - Complete command-line interface guide
- **[Testing Guide](testing.md)** - Testing patterns and best practices

### 📖 **Reference**
Detailed technical documentation:

- **[API Reference](api/)** - Complete API documentation
- **[Performance Guide](performance.md)** - Optimization and tuning
- **[Security Guide](security.md)** - Security best practices
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

## Key Features

### **Multi-Backend Architecture**
Switch between backends without changing your code:
- **Memory**: Fast in-memory caching with LRU eviction
- **Redis**: Distributed caching with clustering and persistence
- **Memcached**: Lightweight distributed caching

### **Intelligent Caching**
- **Auto-Invalidation**: Automatically invalidate cache on database writes
- **Tag-Based Grouping**: Group related cache entries for bulk operations
- **Pattern Matching**: Wildcard-based key operations and cleanup
- **TTL with Jitter**: Prevent thundering herd problems

### **Advanced Search**
- **Vector Similarity**: Semantic search using TF-IDF and multiple distance metrics
- **Fuzzy Matching**: Find approximate matches across cached keys
- **Real-time Indexing**: Automatic search index maintenance

### **Production Features**
- **Metrics & Monitoring**: Prometheus, StatsD, and custom collectors
- **Health Checks**: Monitor cache and backend health
- **Security**: TLS support, input validation, and access controls
- **CLI Tools**: Comprehensive command-line interface

## Installation Options

```bash
# Basic installation
pip install yokedcache

# Full installation (recommended)
pip install yokedcache[full]

# Specific features
pip install yokedcache[vector]      # Vector search
pip install yokedcache[monitoring]  # Prometheus & StatsD
pip install yokedcache[memcached]   # Memcached backend
pip install yokedcache[fuzzy]       # Fuzzy search
```

## What's New in 0.2.0

- **🆕 Multi-Backend Support**: Memory, Redis, and Memcached backends
- **🔍 Vector Search**: Semantic similarity search capabilities  
- **📊 Production Monitoring**: Prometheus and StatsD integration
- **🛠️ Enhanced CLI**: CSV export, file output, and improved UX
- **✅ Comprehensive Testing**: 200+ tests with complete coverage

---

**Ready to get started?** Begin with our [Getting Started Guide](getting-started.md) for a step-by-step introduction.


