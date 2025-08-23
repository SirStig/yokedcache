# Tutorial: SQLAlchemy

## Goal
Cache common SQLAlchemy reads while auto-invalidating after INSERT/UPDATE/DELETE.

## Setup

```python
from yokedcache import YokedCache
from yokedcache.decorators import cached

cache = YokedCache()

@cached(ttl=300, tags=["table:users"])  # function-level caching
async def get_user_by_id(session, user_id: int):
    return session.query(User).filter(User.id == user_id).first()
```

## ORM sessions via dependency wrapper

```python
from yokedcache.decorators import cached_dependency

cached_get_db = cached_dependency(get_session, cache=cache, ttl=300, table_name="users")
```

- Reads are cached; tags include `table:users`.
- On write, call `await db.commit()` to invalidate related tags.
