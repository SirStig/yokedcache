"""
FastAPI example showing YokedCache integration.

This example demonstrates how to integrate YokedCache with a FastAPI
application for automatic database query caching.
"""

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
from typing import List, Optional

from yokedcache import YokedCache, cached_dependency

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./example.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="author")


class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(String)
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    author = relationship("User", back_populates="posts")


# Create tables
Base.metadata.create_all(bind=engine)

# Initialize YokedCache
cache = YokedCache(
    redis_url="redis://localhost:6379/0",
    config_file="cache_config.yaml"  # Optional
)

# FastAPI app
app = FastAPI(title="YokedCache FastAPI Example")


# Original database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Cached database dependency
cached_get_db = cached_dependency(
    get_db,
    cache=cache,
    ttl=300,  # 5 minutes
    auto_invalidate=True
)


# API Routes
@app.get("/users/", response_model=List[dict])
async def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(cached_get_db)):
    """Get users with automatic caching."""
    users = db.query(User).offset(skip).limit(limit).all()
    return [{"id": u.id, "name": u.name, "email": u.email} for u in users]


@app.get("/users/{user_id}", response_model=dict)
async def get_user(user_id: int, db: Session = Depends(cached_get_db)):
    """Get specific user with caching."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at
    }


@app.post("/users/", response_model=dict)
async def create_user(
    name: str,
    email: str,
    db: Session = Depends(cached_get_db)
):
    """Create user - will invalidate user caches automatically."""
    user = User(name=name, email=email)
    db.add(user)
    db.commit()  # This will trigger cache invalidation
    db.refresh(user)
    
    return {"id": user.id, "name": user.name, "email": user.email}


@app.put("/users/{user_id}", response_model=dict)
async def update_user(
    user_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    db: Session = Depends(cached_get_db)
):
    """Update user - will invalidate related caches."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if name:
        user.name = name
    if email:
        user.email = email
    
    db.commit()  # This will trigger cache invalidation
    
    return {"id": user.id, "name": user.name, "email": user.email}


@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(cached_get_db)):
    """Delete user - will invalidate related caches."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()  # This will trigger cache invalidation
    
    return {"message": "User deleted"}


@app.get("/posts/", response_model=List[dict])
async def get_posts(skip: int = 0, limit: int = 100, db: Session = Depends(cached_get_db)):
    """Get posts with caching."""
    posts = db.query(Post).offset(skip).limit(limit).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "content": p.content,
            "author_id": p.author_id,
            "created_at": p.created_at
        }
        for p in posts
    ]


@app.get("/users/{user_id}/posts/", response_model=List[dict])
async def get_user_posts(user_id: int, db: Session = Depends(cached_get_db)):
    """Get posts by user with caching."""
    posts = db.query(Post).filter(Post.author_id == user_id).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "content": p.content,
            "created_at": p.created_at
        }
        for p in posts
    ]


# Cache management endpoints
@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    stats = await cache.get_stats()
    return {
        "hits": stats.total_hits,
        "misses": stats.total_misses,
        "hit_rate": stats.hit_rate,
        "total_keys": stats.total_keys,
        "memory_usage": stats.total_memory_bytes
    }


@app.post("/cache/invalidate")
async def invalidate_cache(pattern: Optional[str] = None, tags: Optional[List[str]] = None):
    """Manually invalidate cache."""
    deleted_count = 0
    
    if pattern:
        deleted_count = await cache.invalidate_pattern(pattern)
    elif tags:
        deleted_count = await cache.invalidate_tags(tags)
    else:
        raise HTTPException(status_code=400, detail="Must provide pattern or tags")
    
    return {"deleted_keys": deleted_count}


@app.get("/cache/search")
async def search_cache(query: str, threshold: int = 80):
    """Perform fuzzy search on cache."""
    results = await cache.fuzzy_search(query, threshold=threshold)
    return {
        "query": query,
        "results": [
            {"key": r.key, "score": r.score, "value": r.value}
            for r in results
        ]
    }


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize cache connection on startup."""
    await cache.connect()
    print("Cache connected successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Close cache connection on shutdown."""
    await cache.disconnect()
    print("Cache disconnected")


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "fastapi_example:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
