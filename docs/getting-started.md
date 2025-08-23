# Getting Started

This guide will walk you through installing YokedCache and setting up your first caching implementation. By the end, you'll have a working cache that dramatically improves your application's performance.

## Installation

### Basic Installation

```bash
# Install the core package
pip install yokedcache
```

### Recommended Installation

For production use, install with all features:

```bash
# Install with all features (recommended)
pip install yokedcache[full]
```

### Feature-Specific Installation

Install only the features you need:

```bash
# Vector similarity search
pip install yokedcache[vector]

# Production monitoring (Prometheus, StatsD)
pip install yokedcache[monitoring]

# Memcached backend support
pip install yokedcache[memcached]

# Fuzzy search capabilities
pip install yokedcache[fuzzy]

# Combine multiple features
pip install yokedcache[vector,monitoring,fuzzy]
```

## Prerequisites

### Redis Setup

YokedCache uses Redis as its default backend. You'll need a Redis instance:

**Option 1: Docker (Recommended for development)**
```bash
# Start Redis with Docker
docker run -d --name redis -p 6379:6379 redis:7

# Verify Redis is running
docker exec redis redis-cli ping
```

**Option 2: Local Installation**
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Windows
# Download and install from https://redis.io/download
```

**Option 3: Cloud Redis**
Use managed Redis services like AWS ElastiCache, Azure Cache for Redis, or Google Cloud Memorystore.

### Verify Installation

Test your YokedCache installation:

```bash
# Check version
python -c "import yokedcache; print(yokedcache.__version__)"

# Test CLI
yokedcache --version

# Test Redis connection
yokedcache ping
```

## Your First Cache

Let's start with a simple example that demonstrates core caching concepts.

### Basic Function Caching

```python
# basic_cache.py
import asyncio
from yokedcache import YokedCache, cached

# Initialize cache (uses Redis at localhost:6379 by default)
cache = YokedCache()

@cached(ttl=300, tags=["api_data"])
async def fetch_user_data(user_id: int):
    """Simulate an expensive API call or database query"""
    print(f"Fetching user {user_id} from database...")  # You'll see this only once
    
    # Simulate slow operation
    await asyncio.sleep(1)
    
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com"
    }

async def main():
    # First call - hits the database (slow)
    print("First call:")
    user = await fetch_user_data(123)
    print(f"Result: {user}")
    
    # Second call - returns cached result (fast)
    print("\nSecond call:")
    user = await fetch_user_data(123)
    print(f"Result: {user}")
    
    # Check cache statistics
    stats = await cache.get_stats()
    print(f"\nCache statistics: {stats}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run this example:
```bash
python basic_cache.py
```

You should see:
- First call takes ~1 second (database hit)
- Second call is instant (cache hit)
- Cache statistics showing hit/miss rates

### Manual Cache Operations

```python
# manual_cache.py
import asyncio
from yokedcache import YokedCache

async def main():
    cache = YokedCache()
    
    # Store data in cache
    await cache.set("user:123", {"name": "Alice", "age": 30}, ttl=300)
    print("Data stored in cache")
    
    # Retrieve data from cache
    user = await cache.get("user:123")
    print(f"Retrieved from cache: {user}")
    
    # Check if key exists
    exists = await cache.exists("user:123")
    print(f"Key exists: {exists}")
    
    # Store with tags for grouping
    await cache.set("product:456", {"name": "Laptop", "price": 999}, 
                   ttl=600, tags=["products", "electronics"])
    
    # Invalidate by tags
    await cache.invalidate_tags(["products"])
    print("Products cache cleared")
    
    # Verify product was removed
    product = await cache.get("product:456")
    print(f"Product after invalidation: {product}")  # Should be None

if __name__ == "__main__":
    asyncio.run(main())
```

## FastAPI Integration

YokedCache shines when integrated with web frameworks like FastAPI.

### Simple FastAPI Example

```python
# fastapi_cache.py
from fastapi import FastAPI, Depends, HTTPException
from yokedcache import YokedCache, cached
import asyncio

app = FastAPI(title="YokedCache Demo")
cache = YokedCache()

# Simulated database
USERS_DB = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
    3: {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
}

@cached(ttl=300, tags=["users"])
async def get_user_from_db(user_id: int):
    """Simulate database query"""
    print(f"Querying database for user {user_id}")
    await asyncio.sleep(0.5)  # Simulate DB latency
    
    user = USERS_DB.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get user by ID (cached)"""
    return await get_user_from_db(user_id)

@app.get("/users")
async def list_users():
    """List all users (cached)"""
    return list(USERS_DB.values())

@app.post("/users/{user_id}/invalidate")
async def invalidate_user_cache(user_id: int):
    """Manually invalidate user cache"""
    await cache.invalidate_tags(["users"])
    return {"message": f"Cache invalidated for user {user_id}"}

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    return await cache.get_stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Run the FastAPI example:
```bash
pip install fastapi uvicorn
python fastapi_cache.py
```

Test the endpoints:
```bash
# Get user (first call - slow)
curl http://localhost:8000/users/1

# Get user again (second call - fast, cached)
curl http://localhost:8000/users/1

# Check cache statistics
curl http://localhost:8000/cache/stats

# Invalidate cache
curl -X POST http://localhost:8000/users/1/invalidate
```

### Database Integration with Auto-Invalidation

For real applications, you'll want automatic cache invalidation when data changes:

```python
# database_integration.py
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from yokedcache import YokedCache, cached_dependency

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)

Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()
cache = YokedCache()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Cached database dependency with auto-invalidation
cached_get_db = cached_dependency(get_db, cache=cache, ttl=300, table_name="users")

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(cached_get_db)):
    """Get user - automatically cached"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/users")
async def create_user(name: str, email: str, db: Session = Depends(cached_get_db)):
    """Create user - automatically invalidates cache on commit"""
    user = User(name=name, email=email)
    db.add(user)
    await db.commit()  # This triggers cache invalidation
    return user

@app.put("/users/{user_id}")
async def update_user(user_id: int, name: str, email: str, db: Session = Depends(cached_get_db)):
    """Update user - automatically invalidates cache on commit"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.name = name
    user.email = email
    await db.commit()  # This triggers cache invalidation
    return user
```

## Configuration

### Basic Configuration

```python
from yokedcache import YokedCache, CacheConfig

# Basic configuration
config = CacheConfig(
    redis_url="redis://localhost:6379/0",
    default_ttl=300,  # 5 minutes default
    key_prefix="myapp"
)

cache = YokedCache(config=config)
```

### Environment-Based Configuration

```bash
# Set environment variables
export YOKEDCACHE_REDIS_URL="redis://localhost:6379/0"
export YOKEDCACHE_DEFAULT_TTL="600"
export YOKEDCACHE_KEY_PREFIX="myapp"
```

```python
# Automatically loads from environment
cache = YokedCache.from_env()
```

### YAML Configuration

```yaml
# config.yaml
redis_url: redis://localhost:6379/0
default_ttl: 300
key_prefix: myapp
enable_fuzzy: true

tables:
  users:
    ttl: 3600
    tags: ["user_data"]
  products:
    ttl: 1800
    tags: ["product_data"]
```

```python
# Load from YAML
cache = YokedCache.from_yaml("config.yaml")
```

## Monitoring and Debugging

### Using the CLI

Monitor your cache in real-time:

```bash
# Test connection
yokedcache ping

# View statistics
yokedcache stats

# Watch statistics (auto-refresh)
yokedcache stats --watch

# List cached keys
yokedcache list --pattern "user:*"

# Search for keys
yokedcache search "alice" --threshold 80
```

### Application Monitoring

```python
import asyncio
from yokedcache import YokedCache

async def monitor_cache():
    cache = YokedCache()
    
    # Get basic statistics
    stats = await cache.get_stats()
    print(f"Hit rate: {stats.hit_rate:.2%}")
    print(f"Total keys: {stats.key_count}")
    print(f"Memory usage: {stats.memory_usage_mb:.2f} MB")
    
    # Health check
    health = await cache.health_check()
    print(f"Cache healthy: {health.is_healthy}")

asyncio.run(monitor_cache())
```

## Next Steps

Now that you have YokedCache working, explore these advanced features:

### 1. **Multi-Backend Support**
Learn about different backends in the [Backend Guide](backends.md):
- Memory backend for development
- Redis backend for production
- Memcached backend for specific use cases

### 2. **Advanced Configuration**
Dive deeper into configuration options in the [Configuration Guide](configuration.md):
- Table-specific settings
- Performance tuning
- Security configurations

### 3. **Usage Patterns**
Explore different ways to use YokedCache in the [Usage Patterns Guide](usage-patterns.md):
- Function caching patterns
- Auto-invalidation strategies
- Fuzzy search capabilities

### 4. **Production Monitoring**
Set up comprehensive monitoring with the [Monitoring Guide](monitoring.md):
- Prometheus integration
- StatsD metrics
- Health checks and alerting

### 5. **Vector Search**
Add semantic search capabilities with the [Vector Search Guide](vector-search.md):
- TF-IDF similarity
- Multiple distance metrics
- Real-time indexing

## Common Issues

### Connection Problems

If you get connection errors:

```bash
# Test Redis connection
redis-cli ping

# Check Redis is running
docker ps | grep redis

# Test YokedCache connection
yokedcache ping --redis-url redis://localhost:6379/0
```

### Import Errors

If imports fail:

```bash
# Verify installation
pip list | grep yokedcache

# Reinstall if needed
pip uninstall yokedcache
pip install yokedcache[full]
```

### Performance Issues

For slow cache operations:

```bash
# Check cache statistics
yokedcache stats

# Monitor operations
yokedcache stats --watch

# Check Redis performance
redis-cli --latency
```

## Getting Help

- **Documentation**: Explore the full documentation for detailed guides
- **Examples**: Check the `examples/` directory for complete working examples
- **CLI Help**: Run `yokedcache --help` for command-line assistance
- **Issues**: Report bugs or request features on GitHub

You're now ready to use YokedCache effectively! Start with simple function caching and gradually explore advanced features as your needs grow.
