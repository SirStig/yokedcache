---
title: FastAPI Redis Caching - YokedCache
description: Add Redis-backed caching to a FastAPI app with auto-invalidation, Prometheus metrics, and a CLI for inspection.
keywords: fastapi redis caching, python caching, cache auto-invalidation, fastapi tutorial
---

# FastAPI + Redis Caching

A focused guide on wiring up Redis-backed caching in a FastAPI app. For a full step-by-step tutorial including SQLAlchemy, analytics caching, and testing, see the [FastAPI tutorial](fastapi.md).

## Installation

```bash
pip install "yokedcache[redis,observability]" fastapi uvicorn
docker run -d --name redis -p 6379:6379 redis:7
```

## Basic setup

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from yokedcache import YokedCache, cached_dependency
from yokedcache.config import CacheConfig
import os

app = FastAPI()

cache = YokedCache(CacheConfig(
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    default_ttl=300,
    key_prefix="myapp",
))

cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(cached_get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/users/{user_id}")
async def update_user(user_id: int, data: UserUpdate, db: Session = Depends(cached_get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(user, k, v)
    await db.commit()  # cache is automatically invalidated
    return user
```

## Production config

```python
config = CacheConfig(
    redis_url=os.getenv("REDIS_URL"),
    max_connections=50,
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    connection_pool_kwargs={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
        "health_check_interval": 30,
    },
    log_level="WARNING",
)
```

Use `rediss://` (TLS) for any Redis not on localhost.

## Prometheus metrics

```bash
pip install "yokedcache[observability]"
```

```python
from yokedcache.monitoring import CacheMetrics, PrometheusCollector

metrics = CacheMetrics([PrometheusCollector(namespace="myapp", port=8000)])
cache = YokedCache(CacheConfig(...), metrics=metrics)

@app.get("/health/cache")
async def cache_health():
    stats = await cache.get_stats()
    return {"hit_rate": f"{stats.hit_rate:.1%}", "healthy": await cache.health()}
```

Metrics endpoint: `http://localhost:8000/metrics`

## Vector search

```python
from yokedcache.vector_search import VectorSimilaritySearch

vector_search = VectorSimilaritySearch(similarity_method="cosine")

@app.get("/search/products")
async def search_products(query: str, threshold: float = 0.5):
    cache_key = f"vector_search:{query}:{threshold}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    results = await cache.vector_search(query=query, threshold=threshold)
    await cache.set(cache_key, results, ttl=3600, tags=["vector_search"])
    return results
```

## CLI management

```bash
yokedcache stats --watch
yokedcache list --pattern "myapp:*"
yokedcache flush --tags "user_data" --confirm
yokedcache search "alice" --threshold 80
```
