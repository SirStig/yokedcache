# Tutorial: FastAPI Integration

This tutorial walks through a complete FastAPI app with cached database queries, auto-invalidation on writes, and cache management endpoints.

## Setup

```bash
pip install "yokedcache[full]" fastapi uvicorn sqlalchemy
docker run -d --name redis -p 6379:6379 redis:7
```

## Step 1: Basic app

Start with a simple app and a database dependency:

```python
# app.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from yokedcache import YokedCache, cached, cached_dependency
from yokedcache.config import CacheConfig

DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    email = Column(String, unique=True)
    active = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## Step 2: Add caching

Replace `get_db` with a cached version. YokedCache wraps the dependency and automatically invalidates the cache when the session commits a write to the `users` table:

```python
cache = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))

# Cached dependency—reads are cached, writes invalidate the "table:users" tag
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(cached_get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/users")
async def list_users(active_only: bool = True, db: Session = Depends(cached_get_db)):
    q = db.query(User)
    if active_only:
        q = q.filter(User.active == True)
    return q.all()
```

## Step 3: Write operations

Any `commit()` through the cached session automatically invalidates the `table:users` tag, so readers see fresh data on the next request:

```python
from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    name: str
    email: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    active: Optional[bool] = None

@app.post("/users")
async def create_user(user: UserCreate, db: Session = Depends(cached_get_db)):
    db_user = User(**user.dict())
    db.add(db_user)
    await db.commit()  # invalidates "table:users"
    return {"id": db_user.id}

@app.put("/users/{user_id}")
async def update_user(user_id: int, user: UserUpdate, db: Session = Depends(cached_get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    for k, v in user.dict(exclude_unset=True).items():
        setattr(db_user, k, v)
    await db.commit()  # invalidates "table:users"
    return db_user

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(cached_get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    await db.commit()  # invalidates "table:users"
    return {"ok": True}
```

## Step 4: Function-level caching

For expensive aggregations that aren't tied to a single table:

```python
from yokedcache import cached

@cached(ttl=600, tags=["analytics"])
async def compute_user_stats(db: Session):
    total = db.query(User).count()
    active = db.query(User).filter(User.active == True).count()
    return {"total": total, "active": active, "inactive": total - active}

@app.get("/analytics/users")
async def user_analytics(db: Session = Depends(get_db)):
    return await compute_user_stats(db)

# Invalidate analytics separately when needed
@app.post("/analytics/invalidate")
async def invalidate_analytics():
    await cache.invalidate_tags(["analytics"])
    return {"ok": True}
```

## Step 5: Cache management endpoints

These are handy for debugging and ops:

```python
@app.get("/cache/stats")
async def cache_stats():
    stats = await cache.get_stats()
    return {"hit_rate": f"{stats.hit_rate:.1%}", "keys": stats.key_count}

@app.get("/cache/health")
async def cache_health():
    return {"healthy": await cache.health()}

@app.post("/cache/flush/users")
async def flush_users():
    await cache.invalidate_tags(["table:users"])
    return {"ok": True}
```

## Step 6: Lifecycle management

Connect/disconnect cleanly using FastAPI's lifespan:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    yield
    await cache.disconnect()

app = FastAPI(lifespan=lifespan)
```

## Testing

The memory backend makes tests fast and self-contained—no Redis needed:

```python
import pytest
from fastapi.testclient import TestClient
from yokedcache import YokedCache, CacheConfig

@pytest.fixture
def test_cache():
    return YokedCache(CacheConfig())  # memory backend

@pytest.fixture
def client(test_cache):
    app.dependency_overrides[cache] = lambda: test_cache
    return TestClient(app)
```

## Production config

```python
config = CacheConfig(
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    default_ttl=300,
    key_prefix=os.getenv("CACHE_PREFIX", "myapp"),
    max_connections=50,
    enable_circuit_breaker=True,
    log_level="WARNING",
)
```

Use `rediss://` and TLS for any Redis not on localhost. Store the URL in an env var or secret manager.
