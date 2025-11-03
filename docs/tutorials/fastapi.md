# Tutorial: FastAPI Integration

Learn how to integrate YokedCache with FastAPI applications for high-performance caching with automatic invalidation.

## What You'll Build

By the end of this tutorial, you'll have a FastAPI application with:
- Cached database queries that dramatically improve response times
- Automatic cache invalidation when data changes
- Real-time monitoring and statistics
- Production-ready error handling

## Prerequisites

```bash
# Install dependencies
pip install yokedcache[full] fastapi uvicorn sqlalchemy psycopg2-binary

# Start Redis (using Docker)
docker run -d --name redis -p 6379:6379 redis:7
```

## Step 1: Basic FastAPI Setup

Create a simple FastAPI application with a database:

```python
# app.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional
import os

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Integer)  # Price in cents
    category = Column(String, index=True)
    active = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="YokedCache FastAPI Tutorial", version="1.0.0")

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Basic endpoints without caching (we'll improve these)
@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/products")
async def list_products(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Product).filter(Product.active == True)
    if category:
        query = query.filter(Product.category == category)
    return query.all()
```

Test the basic setup:
```bash
uvicorn app:app --reload --port 8000
curl http://localhost:8000/users/1
```

## Step 2: Add YokedCache Integration

Now let's add caching to dramatically improve performance:

```python
# Add these imports at the top
from yokedcache import YokedCache, cached, cached_dependency
from yokedcache.models import SerializationMethod
import asyncio
import time

# Initialize cache
cache = YokedCache()

# Create cached database dependency
cached_get_db = cached_dependency(
    get_db,
    cache=cache,
    ttl=300,  # 5 minutes default
    table_name="auto_detect"  # Auto-detect tables from queries
)

# Add performance timing middleware
@app.middleware("http")
async def add_timing_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Cached database operations
@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(cached_get_db)):
    """Get user by ID - cached automatically"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/users")
async def list_users(
    active_only: bool = True,
    limit: int = 100,
    db: Session = Depends(cached_get_db)
):
    """List users - cached with different keys based on parameters"""
    query = db.query(User)
    if active_only:
        query = query.filter(User.active == True)
    return query.limit(limit).all()

@app.get("/products")
async def list_products(
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    db: Session = Depends(cached_get_db)
):
    """List products - cached by category and parameters"""
    query = db.query(Product)
    if active_only:
        query = query.filter(Product.active == True)
    if category:
        query = query.filter(Product.category == category)
    return query.limit(limit).all()

@app.get("/products/{product_id}")
async def get_product(product_id: int, db: Session = Depends(cached_get_db)):
    """Get product by ID - cached automatically"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
```

## Step 3: Add Write Operations with Auto-Invalidation

Add endpoints that modify data and automatically invalidate related cache entries:

```python
from pydantic import BaseModel

# Request models
class UserCreate(BaseModel):
    name: str
    email: str
    active: bool = True

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    active: Optional[bool] = None

class ProductCreate(BaseModel):
    name: str
    description: str
    price: int
    category: str
    active: bool = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    category: Optional[str] = None
    active: Optional[bool] = None

# Write operations with automatic cache invalidation
@app.post("/users", response_model=dict)
async def create_user(user: UserCreate, db: Session = Depends(cached_get_db)):
    """Create user - automatically invalidates user cache on commit"""
    db_user = User(**user.dict())
    db.add(db_user)
    await db.commit()  # This triggers automatic cache invalidation
    await db.refresh(db_user)
    return {"id": db_user.id, "message": "User created successfully"}

@app.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(cached_get_db)
):
    """Update user - automatically invalidates user cache on commit"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update only provided fields
    update_data = user.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    await db.commit()  # Triggers cache invalidation
    await db.refresh(db_user)
    return db_user

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(cached_get_db)):
    """Delete user - automatically invalidates user cache on commit"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(db_user)
    await db.commit()  # Triggers cache invalidation
    return {"message": "User deleted successfully"}

@app.post("/products")
async def create_product(product: ProductCreate, db: Session = Depends(cached_get_db)):
    """Create product - automatically invalidates product cache on commit"""
    db_product = Product(**product.dict())
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return {"id": db_product.id, "message": "Product created successfully"}

@app.put("/products/{product_id}")
async def update_product(
    product_id: int,
    product: ProductUpdate,
    db: Session = Depends(cached_get_db)
):
    """Update product - automatically invalidates product cache on commit"""
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)

    await db.commit()
    await db.refresh(db_product)
    return db_product
```

## Step 4: Add Cache Management Endpoints

Add endpoints to monitor and manage your cache:

```python
@app.get("/cache/stats")
async def cache_stats():
    """Get comprehensive cache statistics"""
    stats = await cache.get_stats()
    return {
        "hit_rate": f"{stats.hit_rate:.2%}",
        "miss_rate": f"{stats.miss_rate:.2%}",
        "total_requests": stats.total_requests,
        "cache_hits": stats.cache_hits,
        "cache_misses": stats.cache_misses,
        "total_keys": stats.key_count,
        "memory_usage_mb": f"{stats.memory_usage_mb:.2f}",
        "uptime_seconds": stats.uptime_seconds
    }

@app.get("/cache/health")
async def cache_health():
    """Check cache health"""
    health = await cache.health_check()
    return {
        "healthy": health.is_healthy,
        "backend_type": health.backend_type,
        "response_time_ms": health.response_time_ms,
        "details": health.details
    }

@app.post("/cache/invalidate/users")
async def invalidate_users_cache():
    """Manually invalidate all user-related cache entries"""
    await cache.invalidate_tags(["table:users"])
    return {"message": "User cache invalidated"}

@app.post("/cache/invalidate/products")
async def invalidate_products_cache():
    """Manually invalidate all product-related cache entries"""
    await cache.invalidate_tags(["table:products"])
    return {"message": "Product cache invalidated"}

@app.post("/cache/invalidate/all")
async def invalidate_all_cache():
    """Clear all cache entries (use with caution!)"""
    await cache.flush_all()
    return {"message": "All cache invalidated"}

@app.get("/cache/keys")
async def list_cache_keys(pattern: Optional[str] = None, limit: int = 100):
    """List cache keys (for debugging)"""
    if pattern:
        keys = await cache.get_keys_by_pattern(pattern, limit=limit)
    else:
        keys = await cache.get_all_keys(limit=limit)
    return {"keys": keys, "count": len(keys)}
```

## Step 5: Add Function-Level Caching

For expensive computations, add function-level caching:

```python
@cached(ttl=600, tags=["analytics"])
async def calculate_user_analytics(db: Session):
    """Expensive analytics calculation - cached for 10 minutes"""
    print("Calculating user analytics...")  # You'll see this only when cache misses

    # Simulate expensive computation
    await asyncio.sleep(2)

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.active == True).count()
    inactive_users = total_users - active_users

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "activity_rate": f"{(active_users / total_users * 100):.1f}%" if total_users > 0 else "0%",
        "calculated_at": datetime.utcnow().isoformat()
    }

@cached(ttl=300, tags=["analytics", "products"])
async def calculate_product_analytics(db: Session, category: Optional[str] = None):
    """Product analytics - cached by category"""
    print(f"Calculating product analytics for category: {category}")

    await asyncio.sleep(1)  # Simulate expensive computation

    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)

    products = query.all()
    total_products = len(products)
    active_products = len([p for p in products if p.active])
    avg_price = sum(p.price for p in products) / total_products if total_products > 0 else 0

    return {
        "category": category or "all",
        "total_products": total_products,
        "active_products": active_products,
        "average_price_cents": int(avg_price),
        "average_price_dollars": f"${avg_price / 100:.2f}",
        "calculated_at": datetime.utcnow().isoformat()
    }

@app.get("/analytics/users")
async def get_user_analytics(db: Session = Depends(get_db)):
    """Get user analytics - cached for performance"""
    return await calculate_user_analytics(db)

@app.get("/analytics/products")
async def get_product_analytics(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get product analytics - cached by category"""
    return await calculate_product_analytics(db, category)
```

## Step 6: Add Production Configuration

Create production-ready configuration:

```python
# config.py
from yokedcache import CacheConfig, TableCacheConfig
from yokedcache.models import SerializationMethod
import os

def get_cache_config():
    """Get cache configuration based on environment"""

    environment = os.getenv("ENVIRONMENT", "development")

    if environment == "production":
        return CacheConfig(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            default_ttl=600,  # 10 minutes default in production
            key_prefix=f"myapp_prod",
            max_connections=100,

            # Table-specific configurations
            tables={
                "users": TableCacheConfig(
                    ttl=3600,  # 1 hour for user data
                    tags={"user_data"},
                    serialization_method=SerializationMethod.JSON
                ),
                "products": TableCacheConfig(
                    ttl=1800,  # 30 minutes for product data
                    tags={"product_data"},
                    serialization_method=SerializationMethod.JSON
                )
            },

            # Enable monitoring
            enable_metrics=True,
            log_level="WARNING"
        )

    elif environment == "staging":
        return CacheConfig(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
            default_ttl=300,
            key_prefix=f"myapp_staging",
            max_connections=50,

            tables={
                "users": TableCacheConfig(ttl=1800, tags={"user_data"}),
                "products": TableCacheConfig(ttl=900, tags={"product_data"})
            },

            enable_metrics=True,
            log_level="INFO"
        )

    else:  # development
        return CacheConfig(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/2"),
            default_ttl=60,  # Short TTL for development
            key_prefix=f"myapp_dev",
            max_connections=10,

            tables={
                "users": TableCacheConfig(ttl=300, tags={"user_data"}),
                "products": TableCacheConfig(ttl=300, tags={"product_data"})
            },

            enable_fuzzy=True,  # Enable fuzzy search in development
            log_level="DEBUG"
        )

# Update your app.py
cache = YokedCache(config=get_cache_config())
```

## Step 7: Testing Your Implementation

Create a comprehensive test script:

```python
# test_cache_performance.py
import asyncio
import time
import httpx
from typing import List

async def test_cache_performance():
    """Test cache performance improvements"""

    base_url = "http://localhost:8000"

    async with httpx.AsyncClient() as client:
        # Test 1: Database query performance
        print("Testing cache performance...")

        # First request (cache miss)
        start_time = time.time()
        response = await client.get(f"{base_url}/users/1")
        first_request_time = time.time() - start_time
        print(f"First request (cache miss): {first_request_time:.3f}s")

        # Second request (cache hit)
        start_time = time.time()
        response = await client.get(f"{base_url}/users/1")
        second_request_time = time.time() - start_time
        print(f"Second request (cache hit): {second_request_time:.3f}s")

        speedup = first_request_time / second_request_time
        print(f"Cache speedup: {speedup:.1f}x faster")

        # Test 2: Analytics caching
        print("\nTesting analytics caching...")

        start_time = time.time()
        response = await client.get(f"{base_url}/analytics/users")
        first_analytics_time = time.time() - start_time
        print(f"First analytics request: {first_analytics_time:.3f}s")

        start_time = time.time()
        response = await client.get(f"{base_url}/analytics/users")
        second_analytics_time = time.time() - start_time
        print(f"Second analytics request: {second_analytics_time:.3f}s")

        analytics_speedup = first_analytics_time / second_analytics_time
        print(f"Analytics cache speedup: {analytics_speedup:.1f}x faster")

        # Test 3: Cache invalidation
        print("\nTesting cache invalidation...")

        # Create a user
        await client.post(f"{base_url}/users", json={
            "name": "Test User",
            "email": "test@example.com"
        })

        # Check cache stats
        stats_response = await client.get(f"{base_url}/cache/stats")
        stats = stats_response.json()
        print(f"Cache hit rate: {stats['hit_rate']}")
        print(f"Total keys: {stats['total_keys']}")

if __name__ == "__main__":
    asyncio.run(test_cache_performance())
```

## Step 8: Monitoring and Maintenance

Add monitoring endpoints and scripts:

```bash
# monitoring.sh
#!/bin/bash

echo "YokedCache FastAPI Application Monitoring"
echo "========================================"

# Check application health
echo "Application Health:"
curl -s http://localhost:8000/cache/health | jq .

echo -e "\nCache Statistics:"
curl -s http://localhost:8000/cache/stats | jq .

echo -e "\nCache Keys (sample):"
curl -s "http://localhost:8000/cache/keys?limit=10" | jq .

echo -e "\nCLI Statistics:"
yokedcache stats --format json | jq .
```

## Running the Complete Example

1. **Start Redis:**
   ```bash
   docker run -d --name redis -p 6379:6379 redis:7
   ```

2. **Create some test data:**
   ```python
   # seed_data.py
   import asyncio
   import httpx

   async def seed_data():
       async with httpx.AsyncClient() as client:
           # Create users
           users = [
               {"name": "Alice Johnson", "email": "alice@example.com"},
               {"name": "Bob Smith", "email": "bob@example.com"},
               {"name": "Charlie Brown", "email": "charlie@example.com"},
           ]

           for user in users:
               await client.post("http://localhost:8000/users", json=user)

           # Create products
           products = [
               {"name": "Laptop", "description": "Gaming laptop", "price": 149999, "category": "electronics"},
               {"name": "Book", "description": "Python programming", "price": 2999, "category": "books"},
               {"name": "Coffee", "description": "Premium coffee", "price": 1299, "category": "food"},
           ]

           for product in products:
               await client.post("http://localhost:8000/products", json=product)

   asyncio.run(seed_data())
   ```

3. **Run the application:**
   ```bash
   uvicorn app:app --reload --port 8000
   python seed_data.py
   python test_cache_performance.py
   ```

4. **Monitor with CLI:**
   ```bash
   yokedcache stats --watch
   ```

## Key Takeaways

1. **Automatic Caching**: Using `cached_dependency` automatically caches database queries
2. **Auto-Invalidation**: Cache entries are automatically cleared when data changes
3. **Performance Gains**: Typical speedups of 10-100x for cached operations
4. **Function Caching**: Use `@cached` decorator for expensive computations
5. **Monitoring**: Built-in statistics and health checks for production monitoring
6. **Configuration**: Environment-specific configurations for development, staging, and production

This tutorial demonstrates a production-ready FastAPI application with comprehensive caching. The patterns shown here can be adapted to any FastAPI application for significant performance improvements.
