# Invalidation

Cache invalidation is "one of the two hard things" in computer science. YokedCache gives you three tools: tags, patterns, and auto-invalidation on DB writes.

---

## Tag-based invalidation

Tags are the recommended approach. They're fast (O(1) in Redis), don't require scanning keys, and work across all backends.

### Setting tags

```python
# On set
await cache.set("product:1", data, ttl=600, tags=["products", "category:electronics"])

# On decorator
@cached(cache=cache, ttl=300, tags=["users", "tenant:acme"])
async def get_user(user_id: int):
    ...

# On cached_dependency (automatic)
cached_get_db = cached_dependency(
    get_db, cache=cache, ttl=300, table_name="users"
)
# → automatically tags reads with "table:users"
```

### Invalidating

```python
# Single tag
await cache.invalidate_tags(["products"])

# Multiple tags — any entry with ANY of these tags is invalidated
await cache.invalidate_tags(["category:electronics", "tenant:acme"])

# Sync version
cache.invalidate_tags_sync(["users"])
```

### Tag naming conventions

Good tag names are specific enough to be useful and generic enough to group related data:

```python
# By table (used by cached_dependency automatically)
"table:users"
"table:products"
"table:orders"

# By entity (for fine-grained invalidation)
f"user:{user_id}"
f"product:{product_id}"

# By feature area
"search_results"
"homepage"
"analytics"
"nav_menu"

# By tenant (multi-tenant apps)
f"tenant:{tenant_id}"
f"tenant:{tenant_id}:users"

# By API version
"api_v1"
"api_v2"
```

### Tag strategy: broad vs narrow

| Approach | Example | Invalidates | When to use |
|----------|---------|-------------|-------------|
| **Table-level** | `"table:users"` | All user data | Simple apps, when any write invalidates all reads |
| **Entity-level** | `f"user:{id}"` | One user's data | When writes only affect one record |
| **Feature-level** | `"homepage"` | Everything on homepage | When homepage aggregates multiple sources |
| **Tenant-level** | `f"tenant:{id}"` | All data for a tenant | Multi-tenant apps |

In practice, combine them:

```python
@cached(cache=cache, ttl=300, tags=["table:users", f"user:{user_id}"])
async def get_user_profile(user_id: int):
    ...

# Full table invalidation (on any user change)
await cache.invalidate_tags(["table:users"])

# Narrow invalidation (just one user)
await cache.invalidate_tags([f"user:{user_id}"])
```

---

## Pattern-based invalidation

Invalidates all keys matching a glob pattern. More flexible than tags but slower on large caches—it requires scanning all keys.

```python
await cache.invalidate_pattern("user:*")          # all user keys
await cache.invalidate_pattern("session:temp:*")  # temporary sessions
await cache.invalidate_pattern("*:v1")            # all v1 entries
```

Sync version:

```python
cache.invalidate_pattern_sync("user:*")
```

**Performance note:** On Redis, this uses `SCAN` + `DEL`. It's fine for small-to-medium caches, but on caches with millions of keys, prefer tag-based invalidation which is O(1).

---

## Auto-invalidation (cached_dependency)

`cached_dependency` instruments a SQLAlchemy session to automatically invalidate cache entries when a write is committed.

```python
from yokedcache import cached_dependency

cached_get_db = cached_dependency(
    get_db,
    cache=cache,
    ttl=300,
    table_name="users",
)
```

Under the hood:

1. Reads through this dependency are tagged with `"table:users"`
2. The session is monitored for `INSERT`, `UPDATE`, `DELETE` statements
3. On `commit()`, `invalidate_tags(["table:users"])` is called automatically
4. Future reads get fresh data from the database

```python
# This read is cached with tag "table:users"
@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    return db.query(User).filter(User.id == user_id).first()

# This write triggers invalidation automatically on commit
@app.post("/users")
async def create_user(data: UserCreate, db=Depends(cached_get_db)):
    user = User(**data.dict())
    db.add(user)
    await db.commit()  # ← invalidates "table:users"
    return user
```

### Multiple tables

If a write touches multiple tables, you can specify multiple dependencies or invalidate manually:

```python
# Option 1: separate cached dependencies per table
cached_users_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")
cached_orders_db = cached_dependency(get_db, cache=cache, ttl=60, table_name="orders")

# Option 2: manual invalidation after multi-table writes
@app.post("/users/{user_id}/checkout")
async def checkout(user_id: int, db=Depends(get_db)):
    create_order(db, user_id)
    update_user_balance(db, user_id)
    db.commit()

    # Invalidate both tables manually
    await cache.invalidate_tags(["table:users", "table:orders"])
    return {"ok": True}
```

### SQL table detection

YokedCache parses SQL to detect which tables a query touches, so it can auto-tag appropriately:

```python
# These are detected automatically:
"SELECT * FROM users WHERE id = ?"            → table: users
"INSERT INTO products (name) VALUES (?)"      → table: products
"UPDATE orders SET status = ? WHERE id = ?"   → table: orders
"DELETE FROM sessions WHERE expired_at < ?"   → table: sessions

# Joins:
"SELECT u.*, p.* FROM users u JOIN profiles p ON u.id = p.user_id"
→ tables: users, profiles
```

For complex queries, specify `table_name` explicitly:

```python
cached_get_db = cached_dependency(
    get_db, cache=cache, ttl=300, table_name="users"
)
```

---

## Manual invalidation

Sometimes the automatic approaches don't fit. Use these escape hatches:

```python
# Delete a specific key
await cache.delete("user:42")
await cache.delete_many(["user:42", "user:43"])

# Invalidate by tag
await cache.invalidate_tags(["users"])

# Invalidate by pattern
await cache.invalidate_pattern("user:*")

# Clear everything (nuclear option—use with care)
await cache.flush_all()
```

---

## Invalidation in distributed systems

When you have multiple services sharing a Redis cache, invalidation can be triggered from any service:

```python
# Service A: writes user data
@app.put("/users/{user_id}")
async def update_user(user_id: int, data: UserUpdate):
    await db.update_user(user_id, data)
    # Invalidate across all services that share this Redis
    await cache.invalidate_tags([f"user:{user_id}", "table:users"])

# Service B: reads user data
# Will see fresh data on next read after Service A invalidates
@app.get("/dashboard/user/{user_id}")
@cached(cache=cache, ttl=300, tags=[f"user:{user_id}"])
async def dashboard(user_id: int):
    return await fetch_user_dashboard(user_id)
```

This works because both services share the same Redis and tag registry.

---

## Invalidation from the CLI

```bash
# By tag
yokedcache flush --tags "table:users" --confirm

# By pattern
yokedcache flush --pattern "session:*" --force

# All
yokedcache flush --all --force
```

---

## Common pitfalls

**Forgetting to invalidate on writes:** If you use `@cached` or manual `cache.set()` without `cached_dependency`, you're responsible for invalidating on writes. Tags help—just invalidate the tag when anything changes.

**Over-invalidating:** Invalidating `"table:users"` on every user write is correct but blunt. If you only changed one user's email, you invalidate everyone's cached user data. For high-read-rate tables, consider entity-level tags like `f"user:{user_id}"`.

**Pattern invalidation on huge caches:** If you have 10M keys, `await cache.invalidate_pattern("user:*")` will scan all of them. Use tag-based invalidation instead—it's O(1) regardless of cache size.

**Race conditions:** There's a small window between a write completing and the cache being invalidated. Applications should tolerate slightly stale data (typically < 1ms). If this is unacceptable, use the write-through pattern: update the cache atomically with the write, rather than invalidating after.
