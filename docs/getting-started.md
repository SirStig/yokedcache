# Getting Started

## Installation

```bash
pip install yokedcache
# With extras
pip install "yokedcache[sqlalchemy,fuzzy]"
```

## Minimal setup

```python
from fastapi import FastAPI, Depends
from yokedcache import YokedCache, cached_dependency

app = FastAPI()
cache = YokedCache(redis_url="redis://localhost:6379/0")

cached_get_db = cached_dependency(get_db, cache=cache, ttl=300)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    return db.query(User).filter(User.id == user_id).first()
```

## Examples

- See `examples/basic_usage.py`
- See `examples/fastapi_example.py`
