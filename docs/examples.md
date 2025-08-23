# Examples

- Repository examples:
  - `examples/basic_usage.py`
  - `examples/fastapi_example.py`
  - `examples/cache_config.yaml`

## Quick snippets

### Decorator caching
```python
from yokedcache import cached

@cached(ttl=600, tags=["products"])  
async def get_expensive_data(q: str):
    return expensive_db_query(q)
```

### Manual operations
```python
from yokedcache import YokedCache
cache = YokedCache()
await cache.set("key", {"data": 1}, ttl=120, tags=["demo"]) 
value = await cache.get("key")
await cache.invalidate_tags(["demo"])  
```
