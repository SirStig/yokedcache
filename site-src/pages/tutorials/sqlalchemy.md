# Tutorial: SQLAlchemy Integration

YokedCache works well with SQLAlchemy in a few different patterns depending on how your app is structured.

## Setup

```bash
pip install "yokedcache[full]" sqlalchemy
docker run -d --name redis -p 6379:6379 redis:7
```

## Pattern 1: Function-level caching

The simplest approach—cache individual query functions with `@cached`:

```python
from yokedcache import YokedCache, cached
from yokedcache.config import CacheConfig

cache = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))

@cached(ttl=600, tags=["users"])
async def get_user_by_id(user_id: int):
    with SessionLocal() as session:
        user = session.query(User).filter(User.id == user_id).first()
        # Return a dict, not the ORM object, so it serializes cleanly
        return {"id": user.id, "name": user.username, "email": user.email} if user else None

@cached(ttl=180, tags=["posts"])
async def get_published_posts(limit: int = 10):
    with SessionLocal() as session:
        posts = session.query(Post).filter(Post.published == True).limit(limit).all()
        return [{"id": p.id, "title": p.title} for p in posts]
```

When you write, invalidate the related tags:

```python
async def create_user(user_data: dict):
    with SessionLocal() as session:
        user = User(**user_data)
        session.add(user)
        session.commit()
        await cache.invalidate_tags(["users"])
        return user.id
```

## Pattern 2: Session-level caching (FastAPI)

Use `cached_dependency` to cache at the session/dependency level. When the session commits a write, the cache is invalidated automatically:

```python
from fastapi import Depends
from yokedcache import cached_dependency

cached_get_session = cached_dependency(
    get_session,
    cache=cache,
    ttl=300,
    table_name="users",
)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_session)):
    return db.query(User).filter(User.id == user_id).first()

@app.post("/users")
async def create_user(data: UserCreate, db=Depends(cached_get_session)):
    user = User(**data.dict())
    db.add(user)
    await db.commit()  # triggers invalidation of "table:users"
    return user
```

See the [FastAPI tutorial](fastapi.md) for a more complete example.

## Pattern 3: Repository pattern

Cache at the repository level for clean separation:

```python
class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    @cached(ttl=600, tags=["users"])
    async def get_by_id(self, user_id: int):
        return self.session.query(User).filter(User.id == user_id).first()

    @cached(ttl=300, tags=["users"])
    async def get_active(self, limit: int = 50):
        return self.session.query(User).filter(User.is_active == True).limit(limit).all()

    async def create(self, data: dict):
        user = User(**data)
        self.session.add(user)
        await self.session.commit()
        await cache.invalidate_tags(["users"])
        return user
```

## Cache warming

Pre-populate the cache before traffic hits. Handy after a deploy or cold start:

```python
import asyncio

async def warm_cache():
    # Concurrently warm the most-accessed entries
    top_user_ids = [1, 2, 3, 4, 5]
    await asyncio.gather(*[get_user_by_id(uid) for uid in top_user_ids])
    await get_published_posts(limit=20)
```

Or use the CLI with a warming config file:

```bash
yokedcache warm --config-file warming.yaml
```

## Serialization note

ORM objects aren't JSON-serializable. Convert them to dicts (or use Pydantic) before caching, or use `SerializationMethod.PICKLE` if you need the full ORM object—though pickle has security implications (see [Security](../security.md)).
