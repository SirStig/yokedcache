---
title: YokedCache
---

# YokedCache

High-Performance Caching for Modern Python Applications

Install:

```bash
pip install yokedcache
```

Quick example:

```python
from fastapi import FastAPI, Depends
from yokedcache import cached_dependency

app = FastAPI()

# Replace your database dependency
cached_get_db = cached_dependency(get_db, ttl=300)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    return db.query(User).filter(User.id == user_id).first()
```

Continue with Getting Started for a guided setup.


