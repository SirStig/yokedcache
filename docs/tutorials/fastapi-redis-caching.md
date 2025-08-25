---
title: Python FastAPI Caching Tutorial - YokedCache
description: Complete tutorial for implementing Redis caching in FastAPI applications using YokedCache. Learn auto-invalidation, vector search caching, and performance optimization.
keywords: fastapi caching tutorial, python redis caching, fastapi redis integration, cache auto-invalidation tutorial
---

# Python FastAPI Caching with Redis Auto-Invalidation

This comprehensive tutorial shows you how to implement high-performance caching in your FastAPI applications using YokedCache, the premier Python caching library for FastAPI with Redis auto-invalidation.

## What You'll Learn

- How to set up Redis caching in FastAPI applications
- Implementing automatic cache invalidation on database changes
- Vector search caching for semantic similarity
- Performance optimization techniques for Python web applications
- Production-ready caching strategies

## Prerequisites

- Python 3.9+
- FastAPI application
- Redis server (local or cloud)
- Basic understanding of async/await

## Step 1: Installation

Install YokedCache with full features for your FastAPI application:

```bash
pip install yokedcache[full]
```

This includes:
- Redis caching backend
- Vector search capabilities
- Monitoring and metrics
- Fuzzy search features

## Step 2: Basic FastAPI Redis Caching Setup

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from yokedcache import YokedCache, cached_dependency
from .database import get_db
from .models import User
from .schemas import UserResponse

app = FastAPI(title="FastAPI with Redis Caching")

# Initialize YokedCache with Redis
cache = YokedCache(
    redis_url="redis://localhost:6379/0",
    default_ttl=300  # 5 minutes default cache
)

# Create cached database dependency
cached_get_db = cached_dependency(
    get_db,
    cache=cache,
    ttl=300,
    tags=["database"]
)

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(cached_get_db)
):
    """
    Get user by ID with automatic Redis caching.

    This endpoint demonstrates:
    - Automatic caching of database queries
    - Cache invalidation on user updates
    - Zero-code caching integration
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db)
):
    """
    Update user with automatic cache invalidation.

    YokedCache automatically invalidates related cache entries
    when database modifications occur.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user data
    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    # Cache is automatically invalidated
    return user
```

## Step 3: Advanced Configuration

Configure YokedCache for production use:

```python
from yokedcache import YokedCache, CacheConfig

# Production configuration
config = CacheConfig(
    redis_url="redis://your-redis-cluster:6379",
    max_connections=50,

    # Circuit breaker for reliability
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_timeout=60.0,

    # Connection pool optimization
    connection_pool_kwargs={
        "socket_connect_timeout": 5.0,
        "socket_timeout": 5.0,
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30
    },

    # Error handling
    fallback_enabled=True,
    connection_retries=3,
    retry_delay=0.1
)

cache = YokedCache(config=config)
```

## Step 4: Vector Search Caching

Implement semantic similarity caching:

```python
from yokedcache.vector_search import VectorSimilaritySearch

# Initialize vector search
vector_search = VectorSimilaritySearch(
    similarity_method="cosine",
    max_features=1000
)

@app.get("/search/products")
async def search_products_semantic(
    query: str,
    threshold: float = 0.5,
    max_results: int = 10
):
    """
    Semantic product search with vector caching.

    Uses TF-IDF and cosine similarity for intelligent
    product recommendations with Redis persistence.
    """
    # Check cache first
    cache_key = f"vector_search:{query}:{threshold}"
    cached_results = await cache.get(cache_key)

    if cached_results:
        return cached_results

    # Perform vector search
    results = await cache.vector_search(
        query=query,
        threshold=threshold,
        max_results=max_results
    )

    # Cache results for 1 hour
    await cache.set(cache_key, results, ttl=3600, tags=["vector_search"])

    return results
```

## Step 5: Monitoring and Metrics

Add production monitoring:

```python
from yokedcache.monitoring import PrometheusCollector, CacheMetrics

# Set up monitoring
prometheus = PrometheusCollector(namespace="fastapi_app")
cache_metrics = CacheMetrics([prometheus])

# Initialize cache with monitoring
cache = YokedCache(
    config=config,
    metrics=cache_metrics
)

@app.get("/health/cache")
async def cache_health():
    """Check Redis cache health and performance metrics."""
    health = await cache.detailed_health_check()
    metrics = cache.get_comprehensive_metrics()

    return {
        "status": health["status"],
        "hit_rate": f"{metrics.hit_rate:.2%}",
        "avg_response_time": f"{metrics.avg_response_time:.3f}s",
        "connections": health["connection_pool"]["available"]
    }
```

## Step 6: CLI Management

Use YokedCache CLI for cache management:

```bash
# Monitor cache performance
yokedcache stats --watch

# Export metrics to CSV
yokedcache stats --format csv --output cache_metrics.csv

# Search cached data
yokedcache search "user data" --method vector --threshold 0.5

# Flush specific cache tags
yokedcache flush --tags "user_data,product_cache"
```

## Best Practices

### 1. Cache Key Strategy
```python
# Use consistent, hierarchical keys
cache_key = f"user:{user_id}:profile"
cache_key = f"product:{category}:{product_id}"
```

### 2. TTL Configuration
```python
# Different TTL for different data types
user_cache_ttl = 3600      # 1 hour for user data
product_cache_ttl = 7200   # 2 hours for product data
search_cache_ttl = 1800    # 30 minutes for search results
```

### 3. Error Handling
```python
try:
    cached_data = await cache.get(cache_key)
    if cached_data is None:
        # Cache miss - fetch from database
        data = await fetch_from_database()
        await cache.set(cache_key, data, ttl=3600)
        return data
    return cached_data
except Exception as e:
    # Log error and fallback to database
    logger.error(f"Cache error: {e}")
    return await fetch_from_database()
```

## Performance Results

With YokedCache implementation:

- **Database Load**: 60-90% reduction
- **API Response Time**: 200-500ms improvement
- **Memory Efficiency**: Optimized serialization
- **Reliability**: 99.9% uptime with circuit breaker

## Next Steps

- Explore [Vector Search Caching](../vector-search.md)
- Learn about [Production Monitoring](../monitoring.md)
- Check out [Advanced Configuration](../configuration.md)
- Read the [Performance Guide](../performance.md)
