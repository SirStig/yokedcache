# Usage Guide

## Function result caching

```python
from yokedcache import cached

@cached(ttl=600, tags=["products"])  # cache function result
async def get_products(category: str):
    ...
```

## FastAPI dependency caching

```python
from fastapi import Depends
from yokedcache import YokedCache, cached_dependency

cache = YokedCache()

cached_get_db = cached_dependency(get_db, cache=cache, ttl=300)

@app.get("/items/{item_id}")
async def read_item(item_id: int, db=Depends(cached_get_db)):
    return db.query(Item).get(item_id)
```

## Manual operations

```python
from yokedcache import YokedCache

cache = YokedCache()
await cache.set("key", {"data": 1}, ttl=120, tags=["demo"]) 
value = await cache.get("key")
await cache.invalidate_tags(["demo"])  # bulk invalidation
```

## Fuzzy search

```python
results = await cache.fuzzy_search("alice", threshold=80, tags={"users"})
```

## Cache warming

```python
from yokedcache.decorators import warm_cache

count = await warm_cache(
    cache,
    [
        {"func": get_products, "args": ["books"], "ttl": 600},
    ],
)
```
