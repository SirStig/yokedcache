"""
Basic usage examples for YokedCache.

This file demonstrates various ways to use YokedCache for caching
in Python applications.
"""

import asyncio
from datetime import datetime
from yokedcache import YokedCache, cached, CacheConfig


async def basic_cache_operations():
    """Demonstrate basic cache operations."""
    print("=== Basic Cache Operations ===")
    
    # Initialize cache
    cache = YokedCache(redis_url="redis://localhost:6379/0")
    
    try:
        # Connect to Redis
        await cache.connect()
        
        # Basic set and get
        await cache.set("user:123", {"name": "Alice", "email": "alice@example.com"}, ttl=300)
        user = await cache.get("user:123")
        print(f"Retrieved user: {user}")
        
        # Set with tags for grouping
        await cache.set(
            "user:124", 
            {"name": "Bob", "email": "bob@example.com"}, 
            ttl=300,
            tags=["users", "active"]
        )
        
        await cache.set(
            "user:125", 
            {"name": "Charlie", "email": "charlie@example.com"}, 
            ttl=300,
            tags=["users", "inactive"]
        )
        
        # Check if key exists
        exists = await cache.exists("user:123")
        print(f"User 123 exists: {exists}")
        
        # Get cache statistics
        stats = await cache.get_stats()
        print(f"Cache hits: {stats.total_hits}, misses: {stats.total_misses}")
        print(f"Hit rate: {stats.hit_rate:.2f}%")
        
    finally:
        await cache.disconnect()


async def tag_based_invalidation():
    """Demonstrate tag-based cache invalidation."""
    print("\n=== Tag-Based Invalidation ===")
    
    cache = YokedCache()
    
    try:
        await cache.connect()
        
        # Set multiple items with tags
        await cache.set("product:1", {"name": "Laptop", "price": 1000}, tags=["products", "electronics"])
        await cache.set("product:2", {"name": "Phone", "price": 500}, tags=["products", "electronics"])
        await cache.set("product:3", {"name": "Book", "price": 20}, tags=["products", "books"])
        
        # Verify items exist
        print(f"Product 1: {await cache.get('product:1')}")
        print(f"Product 2: {await cache.get('product:2')}")
        print(f"Product 3: {await cache.get('product:3')}")
        
        # Invalidate all electronics
        deleted_count = await cache.invalidate_tags(["electronics"])
        print(f"Deleted {deleted_count} electronics items")
        
        # Check what remains
        print(f"Product 1 after invalidation: {await cache.get('product:1')}")  # None
        print(f"Product 2 after invalidation: {await cache.get('product:2')}")  # None
        print(f"Product 3 after invalidation: {await cache.get('product:3')}")  # Still exists
        
    finally:
        await cache.disconnect()


async def pattern_based_invalidation():
    """Demonstrate pattern-based cache invalidation."""
    print("\n=== Pattern-Based Invalidation ===")
    
    cache = YokedCache()
    
    try:
        await cache.connect()
        
        # Set items with predictable key patterns
        await cache.set("session:user:123", {"login_time": datetime.now().isoformat()})
        await cache.set("session:user:124", {"login_time": datetime.now().isoformat()})
        await cache.set("session:admin:125", {"login_time": datetime.now().isoformat()})
        await cache.set("config:app:theme", {"theme": "dark"})
        
        # Invalidate all user sessions
        deleted_count = await cache.invalidate_pattern("session:user:*")
        print(f"Deleted {deleted_count} user session keys")
        
        # Check remaining keys
        print(f"User 123 session: {await cache.get('session:user:123')}")  # None
        print(f"Admin 125 session: {await cache.get('session:admin:125')}")  # Still exists
        print(f"App config: {await cache.get('config:app:theme')}")  # Still exists
        
    finally:
        await cache.disconnect()


async def fuzzy_search_example():
    """Demonstrate fuzzy search capabilities."""
    print("\n=== Fuzzy Search ===")
    
    # Enable fuzzy search in config
    config = CacheConfig(enable_fuzzy=True, fuzzy_threshold=70)
    cache = YokedCache(config=config)
    
    try:
        await cache.connect()
        
        # Set items with searchable content
        await cache.set("user:alice:profile", {"name": "Alice Johnson", "role": "developer"})
        await cache.set("user:bob:profile", {"name": "Bob Smith", "role": "designer"})
        await cache.set("user:charlie:profile", {"name": "Charlie Brown", "role": "manager"})
        await cache.set("product:laptop:details", {"name": "Gaming Laptop", "category": "electronics"})
        
        # Perform fuzzy search
        results = await cache.fuzzy_search("alice", threshold=70, max_results=5)
        
        print(f"Fuzzy search results for 'alice':")
        for result in results:
            print(f"  Key: {result.key}, Score: {result.score}%, Value: {result.value}")
        
        # Search for profiles
        profile_results = await cache.fuzzy_search("profile", threshold=60)
        print(f"\nFuzzy search results for 'profile':")
        for result in profile_results:
            print(f"  Key: {result.key}, Score: {result.score}%")
        
    finally:
        await cache.disconnect()


@cached(ttl=60, tags=["expensive_ops"])
async def expensive_database_operation(query_param):
    """Example of using the @cached decorator."""
    print(f"Executing expensive operation with param: {query_param}")
    
    # Simulate expensive database query
    await asyncio.sleep(1)  # Simulated delay
    
    return {
        "param": query_param,
        "result": f"processed_{query_param}",
        "timestamp": datetime.now().isoformat()
    }


async def decorator_example():
    """Demonstrate using the @cached decorator."""
    print("\n=== Decorator Usage ===")
    
    # First call - will execute function
    start_time = datetime.now()
    result1 = await expensive_database_operation("test_query")
    first_duration = (datetime.now() - start_time).total_seconds()
    print(f"First call result: {result1}")
    print(f"First call duration: {first_duration:.3f} seconds")
    
    # Second call - will use cache
    start_time = datetime.now()
    result2 = await expensive_database_operation("test_query")
    second_duration = (datetime.now() - start_time).total_seconds()
    print(f"Second call result: {result2}")
    print(f"Second call duration: {second_duration:.3f} seconds")
    
    # Should be much faster the second time
    print(f"Speed improvement: {first_duration / second_duration:.1f}x faster")


async def configuration_example():
    """Demonstrate different configuration options."""
    print("\n=== Configuration Example ===")
    
    # Create custom configuration
    config = CacheConfig(
        redis_url="redis://localhost:6379/1",  # Different database
        default_ttl=600,  # 10 minutes
        key_prefix="myapp",
        enable_fuzzy=True,
        fuzzy_threshold=85,
        max_connections=20,
        log_level="DEBUG"
    )
    
    cache = YokedCache(config=config)
    
    try:
        await cache.connect()
        
        # Set value with custom config
        await cache.set("custom:config:test", {"configured": True})
        
        # Get configuration details
        print(f"Key prefix: {cache.config.key_prefix}")
        print(f"Default TTL: {cache.config.default_ttl}")
        print(f"Fuzzy enabled: {cache.config.enable_fuzzy}")
        
        # Verify value was stored
        value = await cache.get("custom:config:test")
        print(f"Retrieved value: {value}")
        
    finally:
        await cache.disconnect()


async def main():
    """Run all examples."""
    print("YokedCache Usage Examples")
    print("=" * 50)
    
    await basic_cache_operations()
    await tag_based_invalidation()
    await pattern_based_invalidation()
    await fuzzy_search_example()
    await decorator_example()
    await configuration_example()
    
    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
