# Tutorial: SQLAlchemy Integration

Learn how to integrate YokedCache with SQLAlchemy for high-performance database caching with intelligent invalidation patterns.

## What You'll Learn

- How to cache SQLAlchemy queries effectively
- Different caching patterns for different use cases
- Automatic cache invalidation on database writes
- Performance optimization techniques
- Production-ready patterns

## Prerequisites

```bash
# Install dependencies
pip install yokedcache[full] sqlalchemy psycopg2-binary

# Start Redis
docker run -d --name redis -p 6379:6379 redis:7
```

## Basic SQLAlchemy Setup

First, let's create a standard SQLAlchemy setup:

```python
# models.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tutorial.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    posts = relationship("Post", back_populates="author")

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True)
    content = Column(Text)
    published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Foreign keys
    author_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    author = relationship("User", back_populates="posts")

# Create tables
Base.metadata.create_all(bind=engine)

# Session factory
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

## Pattern 1: Function-Level Caching

Cache individual database queries using function decorators:

```python
# cached_queries.py
from yokedcache import YokedCache, cached
from models import User, Post, get_session
from typing import List, Optional

# Initialize cache
cache = YokedCache()

@cached(ttl=600, tags=["users"])
async def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID - cached for 10 minutes"""
    with next(get_session()) as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat()
            }
        return None

@cached(ttl=180, tags=["posts"])
async def get_published_posts(limit: int = 10) -> List[dict]:
    """Get published posts - cached for 3 minutes"""
    with next(get_session()) as session:
        posts = (session.query(Post)
                .filter(Post.published == True)
                .order_by(Post.created_at.desc())
                .limit(limit)
                .all())

        return [{
            "id": post.id,
            "title": post.title,
            "content": post.content[:200] + "..." if len(post.content) > 200 else post.content,
            "created_at": post.created_at.isoformat(),
            "author": {
                "id": post.author.id,
                "username": post.author.username,
                "full_name": post.author.full_name
            }
        } for post in posts]

@cached(ttl=900, tags=["analytics"])
async def get_user_stats() -> dict:
    """Get user statistics - cached for 15 minutes"""
    with next(get_session()) as session:
        total_users = session.query(User).count()
        active_users = session.query(User).filter(User.is_active == True).count()
        total_posts = session.query(Post).count()
        published_posts = session.query(Post).filter(Post.published == True).count()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_posts": total_posts,
            "published_posts": published_posts,
            "calculated_at": datetime.utcnow().isoformat()
        }
```

## Pattern 2: Session-Level Caching

Cache at the session level for dependency injection:

```python
# cached_sessions.py
from yokedcache import cached_dependency
from models import get_session

# Create cached session dependency
cached_get_session = cached_dependency(
    get_session,
    cache=cache,
    ttl=300,  # 5 minutes default
    table_name="auto_detect"  # Auto-detect table names from queries
)

# Table-specific cached sessions
users_cached_session = cached_dependency(
    get_session,
    cache=cache,
    ttl=600,  # 10 minutes for user queries
    table_name="users"
)

posts_cached_session = cached_dependency(
    get_session,
    cache=cache,
    ttl=180,  # 3 minutes for post queries
    table_name="posts"
)
```

## Pattern 3: Repository Pattern with Caching

Implement the repository pattern with built-in caching:

```python
# repositories.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from yokedcache import cached
from models import User, Post
from sqlalchemy.orm import Session

class BaseRepository(ABC):
    def __init__(self, session: Session):
        self.session = session

class UserRepository(BaseRepository):

    @cached(ttl=600, tags=["users"])
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID with caching"""
        return self.session.query(User).filter(User.id == user_id).first()

    @cached(ttl=300, tags=["users"])
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username with caching"""
        return self.session.query(User).filter(User.username == username).first()

    @cached(ttl=180, tags=["users"])
    async def get_active_users(self, limit: int = 50) -> List[User]:
        """Get active users with caching"""
        return (self.session.query(User)
                .filter(User.is_active == True)
                .limit(limit)
                .all())

    async def create(self, user_data: Dict[str, Any]) -> User:
        """Create user and invalidate cache"""
        user = User(**user_data)
        self.session.add(user)
        await self.session.commit()

        # Invalidate user-related cache
        await cache.invalidate_tags(["users"])

        return user

class PostRepository(BaseRepository):

    @cached(ttl=300, tags=["posts"])
    async def get_by_id(self, post_id: int) -> Optional[Post]:
        """Get post by ID with caching"""
        return self.session.query(Post).filter(Post.id == post_id).first()

    @cached(ttl=180, tags=["posts"])
    async def get_published(self, limit: int = 10) -> List[Post]:
        """Get published posts with caching"""
        return (self.session.query(Post)
                .filter(Post.published == True)
                .order_by(Post.created_at.desc())
                .limit(limit)
                .all())

    async def create(self, post_data: Dict[str, Any]) -> Post:
        """Create post and invalidate cache"""
        post = Post(**post_data)
        self.session.add(post)
        await self.session.commit()

        # Invalidate post-related cache
        await cache.invalidate_tags(["posts"])

        return post
```

## Cache Warming Strategies

Implement cache warming for frequently accessed data:

```python
# cache_warming.py
import asyncio
from cached_queries import *

async def warm_user_cache(user_ids: List[int]):
    """Warm cache for specific users"""
    print(f"Warming cache for {len(user_ids)} users...")

    tasks = []
    for user_id in user_ids:
        tasks.append(get_user_by_id(user_id))

    await asyncio.gather(*tasks)
    print("User cache warmed successfully")

async def warm_popular_content():
    """Warm cache for popular content"""
    print("Warming popular content cache...")

    # Warm popular posts
    await get_published_posts(limit=20)

    # Warm user statistics
    await get_user_stats()

    print("Popular content cache warmed successfully")

async def full_cache_warm():
    """Perform full cache warming"""
    print("Starting full cache warming...")

    # Warm user cache for first 50 users
    user_ids = list(range(1, 51))
    await warm_user_cache(user_ids)

    # Warm popular content
    await warm_popular_content()

    print("Full cache warming completed")
```

## Performance Monitoring

Monitor cache performance and database query patterns:

```python
# monitoring.py
import time
import asyncio
from contextlib import asynccontextmanager

class QueryPerformanceMonitor:
    def __init__(self):
        self.query_stats = {}

    @asynccontextmanager
    async def monitor_query(self, query_name: str):
        """Context manager to monitor query performance"""
        start_time = time.time()

        try:
            yield
        finally:
            end_time = time.time()
            execution_time = end_time - start_time

            if query_name not in self.query_stats:
                self.query_stats[query_name] = {
                    "total_calls": 0,
                    "total_time": 0,
                    "avg_time": 0
                }

            stats = self.query_stats[query_name]
            stats["total_calls"] += 1
            stats["total_time"] += execution_time
            stats["avg_time"] = stats["total_time"] / stats["total_calls"]

    def get_stats(self):
        """Get performance statistics"""
        return self.query_stats

# Global monitor instance
monitor = QueryPerformanceMonitor()

async def performance_test():
    """Test cache performance vs database performance"""
    print("Running performance tests...")

    user_id = 1

    # First call (cache miss)
    async with monitor.monitor_query("cached_user_first_call"):
        await get_user_by_id(user_id)

    # Second call (cache hit)
    async with monitor.monitor_query("cached_user_second_call"):
        await get_user_by_id(user_id)

    # Print statistics
    stats = monitor.get_stats()
    for query_name, query_stats in stats.items():
        print(f"{query_name}: {query_stats['avg_time']:.4f}s avg")
```

## Best Practices Summary

### 1. Cache TTL Strategy
- **Hot data** (frequently changing): 30-300 seconds
- **Warm data** (occasionally changing): 300-1800 seconds
- **Cold data** (rarely changing): 1800-3600 seconds
- **Analytics data** (expensive to compute): 900-3600 seconds

### 2. Cache Key Design
- Use descriptive function names for automatic key generation
- Include all relevant parameters in function signatures
- Consider using table-specific tags for easier invalidation

### 3. Invalidation Strategy
- Use `cached_dependency` for automatic invalidation on writes
- Group related data with common tags
- Implement manual invalidation for complex scenarios

### 4. Performance Optimization
- Cache expensive queries and computations
- Monitor cache hit rates and adjust TTL values accordingly
- Implement cache warming for critical data

This SQLAlchemy integration tutorial demonstrates key patterns for implementing high-performance caching in database-driven applications.
