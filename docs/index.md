---
title: YokedCache - Python Caching Library for FastAPI with Redis Auto-Invalidation
description: High-performance Python caching library with Redis auto-invalidation, vector search caching, and seamless FastAPI integration. Enterprise-grade caching solution.
keywords: python caching, fastapi caching, redis caching, cache invalidation, vector search caching, python redis, fastapi redis, cache library python
---

# YokedCache - Python Caching Library for FastAPI

**High-Performance Redis Caching with Auto-Invalidation for Modern Python Applications**

YokedCache is a powerful, async-first Python caching library that brings enterprise-grade Redis caching capabilities to FastAPI applications. With multi-backend support, intelligent auto-invalidation, and production-ready monitoring, it's designed to scale from development to enterprise deployment.

## Why Choose YokedCache for Python FastAPI Development?

- **🚀 Performance**: Async-first design with Redis connection pooling and batch operations
- **🔧 Flexible**: Multiple backends (Memory, Redis, Memcached) with unified Python API
- **🧠 Intelligent**: Auto-invalidation, vector search caching, and fuzzy matching
- **📊 Observable**: Built-in metrics, monitoring, and comprehensive CLI tools
- **🛡️ Production-Ready**: Health checks, error handling, and security features
- **🔐 Resilient**: Circuit breaker, retry logic, and graceful fallbacks *(v0.2.1)*
- **⚡ Enhanced**: Smart async/sync context handling and performance optimizations *(v0.2.1)*
- **🌐 Advanced Patterns**: HTTP middleware, single-flight protection, stale-while-revalidate *(v0.3.0)*
- **🔍 Observability**: OpenTelemetry tracing and per-prefix backend routing *(v0.3.0)*

## Quick Start - Python FastAPI Redis Caching

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

### 💻 **Usage Guide**
Learn different ways to use YokedCache:

- **[Usage Patterns](usage-patterns.md)** - Function caching, auto-invalidation, and fuzzy search
- **[FastAPI Integration](tutorials/fastapi.md)** - Complete FastAPI tutorial with examples
- **[SQLAlchemy Integration](tutorials/sqlalchemy.md)** - Database ORM integration patterns

### 🔍 **Advanced Features**
Powerful capabilities for complex use cases:

- **[Backends & Setup](backends.md)** - Memory, Redis, Memcached backends with setup guides
- **[Vector Search](vector-search.md)** - Semantic similarity search capabilities
- **[Monitoring & Health](monitoring.md)** - Comprehensive monitoring, health checks, and alerting *(v0.2.1)*
- **[Advanced Caching Patterns](usage-patterns.md#advanced-caching-patterns-v030)** - HTTP middleware, SWR, single-flight protection *(v0.3.0)*

### 📖 **Reference**
Detailed technical documentation:

- **[CLI Tool](cli.md)** - Complete command-line interface guide
- **[Performance Guide](performance.md)** - Optimization and tuning
- **[Security Guide](security.md)** - Security best practices
- **[Testing Guide](testing.md)** - Testing patterns and best practices
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- **[API Reference](api/index.md)** - Complete API documentation

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
pip install yokedcache[disk]        # DiskCache backend (v0.3.0)
pip install yokedcache[tracing]     # OpenTelemetry tracing (v0.3.0)
```

## What's New in 0.3.0

- **🌐 HTTP Response Middleware**: ETag/Cache-Control headers with 304 Not Modified responses
- **🛡️ Single-Flight Protection**: Prevents cache stampede with automatic deduplication
- **🔄 Stale-While-Revalidate**: Serve stale data while refreshing in background
- **💪 Stale-If-Error**: Fallback to cached data during service failures
- **🔀 Per-Prefix Routing**: Shard cache keys across multiple backends by prefix
- **📊 OpenTelemetry Integration**: Distributed tracing with spans and metrics
- **💾 New Backends**: DiskCache and SQLite backends for persistent caching

## What's New in 0.2.0

- **🆕 Multi-Backend Support**: Memory, Redis, and Memcached backends
- **🔍 Vector Search**: Semantic similarity search capabilities
- **📊 Production Monitoring**: Prometheus and StatsD integration
- **🛠️ Enhanced CLI**: CSV export, file output, and improved UX
- **✅ Comprehensive Testing**: 200+ tests with complete coverage

---

**Ready to get started?** Begin with our [Getting Started Guide](getting-started.md) for a step-by-step introduction.
