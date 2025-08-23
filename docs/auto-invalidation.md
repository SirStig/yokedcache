# Auto-Invalidation

YokedCache invalidates relevant cache entries on database writes so you don't serve stale data.

## How it works

- Wrap your DB dependency with `cached_dependency(...)`.
- Reads (`query`, `get`, `first`, `all`) are cached with tags like `table:<name>`.
- Writes (`execute`, `exec`) are tracked; on `commit()`, tags for affected tables are invalidated.

```python
from yokedcache import YokedCache
from yokedcache.decorators import cached_dependency

cache = YokedCache()
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

# In your route handlers, use db=Depends(cached_get_db)
```

Under the hood (`yokedcache.decorators.CachedDatabaseWrapper`):

- Extracts table with `extract_table_from_query()` for simple SQL patterns.
- Adds tag `table:<table>` on cached reads.
- On commit, calls `cache.invalidate_tags([f"table:{table}"])`.

## Best practices

- Pass `table_name` when you know the target table.
- Use predictable SQL (or ORM) so table extraction works well.
- For multi-table writes, consider multiple tags.
- For complex cases, call `await cache.invalidate_pattern("users:*")` directly.

