# Tutorial: FastAPI Integration

## Goal
Cache DB reads and auto-invalidate on writes in a FastAPI app.

## Steps

1) Install and set up cache
```bash
pip install yokedcache
```

```python
from fastapi import FastAPI, Depends
from yokedcache import YokedCache
from yokedcache.decorators import cached_dependency

app = FastAPI()
cache = YokedCache(redis_url="redis://localhost:6379/0")

cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    return db.query(User).filter(User.id == user_id).first()
```

2) Commit on writes to trigger invalidation
```python
@app.post("/users")
async def create_user(user: UserIn, db=Depends(cached_get_db)):
    db.add(User(**user.model_dict()))
    await db.commit()  # triggers invalidation of table:users
    return {"ok": True}
```

3) Monitor
```bash
yokedcache stats --watch
```
