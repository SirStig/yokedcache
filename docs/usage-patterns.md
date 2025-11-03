# Usage Patterns

YokedCache offers several patterns for caching data in your applications. Choose the approach that best fits your use case and architectural needs.

## Function Caching

The most straightforward way to add caching to your application is through function decorators.

### Basic Function Caching

Use the `@cached` decorator to cache function results:

```python
from yokedcache import cached

@cached(ttl=600, tags=["products"])
async def get_products(category: str, active_only: bool = True):
    """Expensive database query or API call"""
    return await database.fetch_products(category, active_only)

# First call hits the database
products = await get_products("electronics", active_only=True)

# Second call returns cached result
products = await get_products("electronics", active_only=True)
```

### Advanced Function Caching

Customize caching behavior with additional parameters:

```python
from yokedcache import cached
from yokedcache.models import SerializationMethod

@cached(
    ttl=1800,                                    # 30 minutes
    tags=["user_data", "api_v1"],              # Multiple tags
    serialization=SerializationMethod.PICKLE,   # Custom serialization
    cache_key_prefix="api"                      # Custom key prefix
)
async def get_user_profile(user_id: int, include_permissions: bool = False):
    profile = await database.get_user(user_id)
    if include_permissions:
        profile.permissions = await database.get_user_permissions(user_id)
    return profile
```

### Conditional Caching

Skip caching based on runtime conditions:

```python
@cached(ttl=300, tags=["search_results"])
async def search_products(query: str, use_cache: bool = True):
    if not use_cache:
        # Skip cache for this call
        return await perform_live_search(query)

    return await database.search_products(query)

# Force fresh data
results = await search_products("laptop", use_cache=False)
```

## Manual Cache Operations

For more control, use YokedCache directly for manual cache operations.

### Basic Operations

```python
from yokedcache import YokedCache

cache = YokedCache()

# Store data
await cache.set("user:123", {"name": "John", "email": "john@example.com"}, ttl=300)

# Retrieve data
user = await cache.get("user:123")

# Check if key exists
exists = await cache.exists("user:123")

# Delete specific key
await cache.delete("user:123")
```

### Batch Operations

Perform multiple operations efficiently:

```python
# Set multiple keys at once
data = {
    "user:123": {"name": "John"},
    "user:124": {"name": "Jane"},
    "user:125": {"name": "Bob"}
}
await cache.set_many(data, ttl=300, tags=["user_data"])

# Get multiple keys
keys = ["user:123", "user:124", "user:125"]
results = await cache.get_many(keys)

# Delete multiple keys
await cache.delete_many(keys)
```

### Tag-Based Operations

Use tags to group and manage related cache entries:

```python
# Store with tags
await cache.set("product:1", product_data, ttl=600, tags=["products", "category:electronics"])
await cache.set("product:2", product_data, ttl=600, tags=["products", "category:books"])

# Invalidate by tags
await cache.invalidate_tags(["products"])           # Clear all products
await cache.invalidate_tags(["category:electronics"]) # Clear electronics only

# Pattern-based invalidation
await cache.invalidate_pattern("user:*")           # Clear all user data
await cache.invalidate_pattern("session:temp:*")   # Clear temporary sessions
```

## FastAPI Integration

YokedCache integrates seamlessly with FastAPI through dependency caching.

### Database Dependency Caching

Replace your database dependencies with cached versions:

```python
from fastapi import FastAPI, Depends
from yokedcache import YokedCache, cached_dependency

app = FastAPI()
cache = YokedCache()

# Original database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Cached version
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    # Database queries are automatically cached
    return db.query(User).filter(User.id == user_id).first()
```

### Custom Dependencies

Cache any dependency, not just database connections:

```python
from yokedcache import cached_dependency

# Cache external API client
def get_external_api():
    return ExternalAPIClient(api_key=settings.api_key)

cached_api = cached_dependency(get_external_api, cache=cache, ttl=3600)

@app.get("/external-data/{resource_id}")
async def get_external_data(resource_id: str, api=Depends(cached_api)):
    return await api.fetch_resource(resource_id)

# Cache configuration objects
def get_config():
    return load_configuration_from_database()

cached_config = cached_dependency(get_config, cache=cache, ttl=600)

@app.get("/settings")
async def get_settings(config=Depends(cached_config)):
    return config.public_settings
```

## Auto-Invalidation

Auto-invalidation automatically clears cache entries when related data changes, ensuring you never serve stale data.

### How Auto-Invalidation Works

1. **Read Operations**: Cached with appropriate tags based on tables/entities
2. **Write Operations**: Tracked and queued for invalidation
3. **Transaction Commit**: Triggers invalidation of affected tags
4. **Cache Cleared**: Related entries automatically removed

### Database Write Tracking

YokedCache automatically tracks database writes and invalidates related cache entries:

```python
from yokedcache import YokedCache
from yokedcache.decorators import cached_dependency

cache = YokedCache()
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

# Read operations are cached with "table:users" tag
@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(cached_get_db)):
    # This query result is cached with tag "table:users"
    return db.query(User).filter(User.id == user_id).first()

# Write operations trigger automatic invalidation
@app.post("/users")
async def create_user(user: UserCreate, db=Depends(cached_get_db)):
    new_user = User(**user.dict())
    db.add(new_user)
    await db.commit()  # Automatically invalidates "table:users" tag
    return new_user

@app.put("/users/{user_id}")
async def update_user(user_id: int, user: UserUpdate, db=Depends(cached_get_db)):
    db.query(User).filter(User.id == user_id).update(user.dict())
    await db.commit()  # Automatically invalidates "table:users" tag
    return {"status": "updated"}
```

### Automatic Table Detection

YokedCache extracts table names from SQL queries automatically:

```python
# These patterns are automatically detected:
"SELECT * FROM users WHERE id = ?"           # → table: users
"INSERT INTO products (name) VALUES (?)"     # → table: products
"UPDATE orders SET status = ? WHERE id = ?"  # → table: orders
"DELETE FROM sessions WHERE expired < ?"     # → table: sessions

# Complex JOIN queries
"SELECT u.*, p.name FROM users u JOIN profiles p ON u.id = p.user_id"  # → tables: users, profiles
```

### Manual Invalidation Control

For complex scenarios, manually control invalidation:

```python
# Specify table explicitly
cached_get_db = cached_dependency(
    get_db,
    cache=cache,
    ttl=300,
    table_name="users"  # Explicit table specification
)

# Multiple table invalidation
@app.post("/users/{user_id}/change-role")
async def change_user_role(user_id: int, role: str, db=Depends(cached_get_db)):
    # This operation affects both users and permissions
    db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    db.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))

    # Manually invalidate multiple tables
    await cache.invalidate_tags(["table:users", "table:user_permissions"])

    await db.commit()
    return {"status": "role_changed"}
```

### Cross-Service Invalidation

Invalidate cache across multiple services:

```python
# Service A: User management
@app.put("/users/{user_id}")
async def update_user(user_id: int, user: UserUpdate):
    # Update user in database
    await update_user_in_db(user_id, user)

    # Invalidate user-related cache across all services
    await cache.invalidate_tags([f"user:{user_id}", "table:users"])

    # Optionally publish event for other services
    await publish_user_updated_event(user_id)

# Service B: Order management
@app.get("/orders/user/{user_id}")
async def get_user_orders(user_id: int, db=Depends(cached_get_db)):
    # This will use fresh user data after the update in Service A
    return db.query(Order).filter(Order.user_id == user_id).all()
```

## Fuzzy Search

Find approximate matches across cached keys and optionally search within cached values.

### Enabling Fuzzy Search

```python
# Install the fuzzy search dependencies
# pip install "yokedcache[fuzzy]"

from yokedcache import YokedCache, CacheConfig

# Enable fuzzy search in configuration
config = CacheConfig(
    enable_fuzzy=True,
    fuzzy_threshold=80  # Minimum similarity score (0-100)
)
cache = YokedCache(config=config)
```

### Basic Fuzzy Search

Search for approximate matches in cache keys:

```python
# Store some user data
await cache.set("user:alice_johnson", {"name": "Alice Johnson"}, tags={"users"})
await cache.set("user:bob_alice", {"name": "Bob Alice"}, tags={"users"})
await cache.set("user:charlie_brown", {"name": "Charlie Brown"}, tags={"users"})

# Search for keys containing "alice" (case-insensitive, approximate)
results = await cache.fuzzy_search("alice", threshold=70)

for result in results:
    print(f"Key: {result.key}, Score: {result.score}")
# Output:
# Key: user:alice_johnson, Score: 85
# Key: user:bob_alice, Score: 78
```

### Advanced Fuzzy Search

Customize search parameters for better results:

```python
# Search with filtering and limits
results = await cache.fuzzy_search(
    query="alice",
    threshold=80,           # Higher threshold for more precise matches
    max_results=10,         # Limit number of results
    tags={"users"}          # Only search within user-tagged entries
)

# Search with custom similarity method
results = await cache.fuzzy_search(
    query="alice",
    threshold=75,
    similarity_method="partial_ratio"  # Better for substring matches
)
```

### CLI Fuzzy Search

Use the command line for interactive fuzzy search:

```bash
# Basic search
yokedcache search "alice" --threshold 80

# Search with filters
yokedcache search "alice" --threshold 80 --max-results 5

# Search specific tags
yokedcache search "alice" --tags users,active

# Export results to file
yokedcache search "alice" --threshold 80 --output results.json
```

### Search Within Values

Search not just keys, but also cached values:

```python
# Store structured data
user_data = {
    "name": "Alice Johnson",
    "email": "alice@example.com",
    "department": "Engineering",
    "skills": ["Python", "JavaScript", "Machine Learning"]
}
await cache.set("user:123", user_data, tags={"users"})

# Search within cached values (requires additional configuration)
results = await cache.fuzzy_search_values(
    query="Machine Learning",
    threshold=80,
    search_fields=["skills", "department"]  # Specify which fields to search
)
```

### Fuzzy Search Best Practices

- **Meaningful Keys**: Use descriptive keys that benefit from fuzzy matching
- **Appropriate Thresholds**: Start with 80, adjust based on your data
- **Tag Filtering**: Use tags to limit search scope and improve performance
- **Index Management**: Fuzzy search maintains an index; consider rebuild frequency
- **Performance**: Fuzzy search is slower than exact lookups; use judiciously

## Cache Warming

Pre-populate cache with frequently accessed data to improve initial performance.

### Programmatic Cache Warming

```python
from yokedcache.decorators import warm_cache

# Define warming functions
warming_tasks = [
    {"func": get_products, "args": ["electronics"], "ttl": 600},
    {"func": get_products, "args": ["books"], "ttl": 600},
    {"func": get_user_profile, "args": [123], "kwargs": {"include_permissions": True}, "ttl": 300},
]

# Warm the cache
warmed_count = await warm_cache(cache, warming_tasks)
print(f"Warmed {warmed_count} cache entries")
```

### Configuration-Based Warming

```yaml
# cache_warming.yaml
warming_tasks:
  - function: get_products
    args: ["electronics"]
    ttl: 600
    tags: ["products", "category:electronics"]

  - function: get_popular_items
    args: []
    ttl: 1800
    tags: ["popular", "homepage"]

  - function: get_user_preferences
    args: [123, 456, 789]  # Warm for multiple users
    ttl: 300
    tags: ["user_data"]
```

```python
# Load and execute warming configuration
with open("cache_warming.yaml") as f:
    warming_config = yaml.safe_load(f)

await execute_warming_config(cache, warming_config)
```

### CLI Cache Warming

```bash
# Warm cache using configuration file
yokedcache warm --config-file cache_warming.yaml

# Warm specific functions
yokedcache warm --function get_products --args electronics --ttl 600

# Monitor warming progress
yokedcache warm --config-file cache_warming.yaml --verbose
```

## Error Handling Patterns

Implement robust error handling for cache operations.

### Graceful Degradation

```python
async def get_user_data(user_id: int):
    try:
        # Try cache first
        cached_data = await cache.get(f"user:{user_id}")
        if cached_data is not None:
            return cached_data
    except Exception as e:
        # Cache error - log but continue
        logger.warning(f"Cache read failed: {e}")

    # Fallback to database
    user_data = await database.get_user(user_id)

    try:
        # Try to cache for next time
        await cache.set(f"user:{user_id}", user_data, ttl=300)
    except Exception as e:
        # Cache write error - log but return data
        logger.warning(f"Cache write failed: {e}")

    return user_data
```

### Circuit Breaker Pattern

```python
from datetime import datetime, timedelta

class CacheCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call_with_fallback(self, cache_operation, fallback_operation):
        if self.state == "OPEN":
            if datetime.now() - self.last_failure > timedelta(seconds=self.timeout):
                self.state = "HALF_OPEN"
            else:
                return await fallback_operation()

        try:
            result = await cache_operation()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure = datetime.now()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"

            logger.warning(f"Cache operation failed: {e}")
            return await fallback_operation()

# Usage
circuit_breaker = CacheCircuitBreaker()

async def get_with_fallback(key):
    return await circuit_breaker.call_with_fallback(
        lambda: cache.get(key),
        lambda: database.get_data(key)
    )
```

## Performance Optimization Patterns

### Connection Reuse

```python
# Good: Reuse single cache instance
cache = YokedCache()

async def handler1():
    return await cache.get("key1")

async def handler2():
    return await cache.get("key2")

# Bad: Creating new instances
async def bad_handler():
    cache = YokedCache()  # Don't do this
    return await cache.get("key")
```

### Batch Operations

```python
# Good: Batch multiple operations
keys = [f"user:{i}" for i in user_ids]
users = await cache.get_many(keys)

# Bad: Individual operations in loop
users = {}
for user_id in user_ids:
    users[user_id] = await cache.get(f"user:{user_id}")  # Inefficient
```

### Optimal TTL Strategy

```python
# Hot data: Short TTL
@cached(ttl=30)
async def get_live_prices():
    return await fetch_stock_prices()

# Warm data: Medium TTL
@cached(ttl=300)
async def get_user_profile(user_id):
    return await database.get_user(user_id)

# Cold data: Long TTL
@cached(ttl=3600)
async def get_system_config():
    return await database.get_config()
```

These usage patterns provide a foundation for implementing effective caching strategies in your applications. Choose the patterns that best fit your use case and combine them as needed for optimal performance.
