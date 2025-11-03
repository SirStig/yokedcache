"""
YokedCache Advanced Features Demo

This example demonstrates the new advanced caching features introduced in v0.3.0:
- HTTP Response Middleware
- Single-Flight Protection
- Stale-While-Revalidate
- Per-Prefix Backend Routing
- OpenTelemetry Tracing
- Additional Backends (DiskCache, SQLite)
"""

import asyncio
import time

from fastapi import FastAPI, HTTPException

from yokedcache import CacheConfig, YokedCache
from yokedcache.backends import DiskCacheBackend, SQLiteBackend
from yokedcache.middleware import HTTPCacheMiddleware
from yokedcache.tracing import initialize_tracing


async def main():
    """Demonstrate all advanced caching features."""

    print("🚀 YokedCache Advanced Features Demo")
    print("=" * 50)

    # 1. Initialize OpenTelemetry tracing
    print("\n1. Setting up OpenTelemetry tracing...")
    global_tracer = initialize_tracing(
        service_name="yokedcache-demo", enabled=True, sample_rate=1.0
    )
    print("✓ OpenTelemetry tracing initialized")

    # 2. Configure cache with advanced features
    print("\n2. Configuring cache with advanced features...")
    config = CacheConfig(
        redis_url="redis://localhost:6379",
        enable_stale_while_revalidate=True,
        enable_stale_if_error=True,
        enable_tracing=True,
        stale_if_error_ttl=300,  # 5 minutes
    )

    cache = YokedCache(config)
    print("✓ Cache configured with SWR and tracing")

    # 3. Setup per-prefix backend routing
    print("\n3. Setting up per-prefix backend routing...")

    # Initialize additional backends
    disk_backend = DiskCacheBackend("/tmp/yokedcache_demo")
    sqlite_backend = SQLiteBackend("/tmp/demo_cache.db")

    await disk_backend.connect()
    await sqlite_backend.connect()

    # Setup prefix routing
    cache.setup_prefix_routing()
    cache.add_backend_route("temp:", disk_backend)
    cache.add_backend_route("user:", sqlite_backend)
    # Default backend (Redis) handles all other prefixes

    print("✓ Prefix routing configured:")
    print("  - temp:* -> DiskCache (/tmp/yokedcache_demo)")
    print("  - user:* -> SQLite (/tmp/demo_cache.db)")
    print("  - *      -> Redis (default)")

    # 4. Demonstrate single-flight protection
    print("\n4. Testing single-flight protection...")

    async def expensive_computation(key: str) -> str:
        """Simulate an expensive operation."""
        print(f"   💰 Running expensive computation for {key}...")
        await asyncio.sleep(2)  # Simulate work
        return f"computed_result_for_{key}_{int(time.time())}"

    # Launch multiple concurrent requests for the same key
    start_time = time.time()
    tasks = []
    for i in range(5):
        task = asyncio.create_task(
            cache.fetch_or_set(
                "expensive_operation",
                lambda: expensive_computation("expensive_operation"),
                ttl=60,
            )
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    end_time = time.time()

    print(f"✓ Single-flight protection working:")
    print(f"  - 5 concurrent requests completed in {end_time - start_time:.2f}s")
    print(f"  - All results identical: {all(r == results[0] for r in results)}")
    print(f"  - Result: {results[0]}")

    # 5. Test per-prefix routing
    print("\n5. Testing per-prefix backend routing...")

    # Store data in different backends based on prefix
    test_data = {
        "temp:session_123": {"session_id": "123", "user_id": 456},
        "user:profile_456": {"name": "John Doe", "email": "john@example.com"},
        "cache:general": {"data": "This goes to Redis default backend"},
    }

    for key, value in test_data.items():
        await cache.set(key, value, ttl=300)
        retrieved = await cache.get(key)
        print(f"✓ {key} -> {type(cache._prefix_router.get_backend(key)).__name__}")

    # 6. Demonstrate stale-while-revalidate
    print("\n6. Testing stale-while-revalidate...")

    # Store initial data
    await cache.set("swr_test", "initial_value", ttl=2)
    print("✓ Stored initial value with 2s TTL")

    # Wait for data to become stale
    await asyncio.sleep(3)

    # This should return stale data and trigger background refresh
    async def refresh_function():
        print("   🔄 Background refresh triggered")
        await asyncio.sleep(1)
        return "refreshed_value"

    # The first call returns stale data immediately
    start_time = time.time()
    result = await cache.fetch_or_set("swr_test", refresh_function, ttl=60)
    response_time = time.time() - start_time

    print(f"✓ SWR response in {response_time:.3f}s")
    print(f"  - Immediate result: {result}")

    # Wait for background refresh to complete
    await asyncio.sleep(2)

    # Second call should return fresh data
    fresh_result = await cache.get("swr_test")
    print(f"  - After refresh: {fresh_result}")

    # 7. Demonstrate distributed tracing
    print("\n7. Testing OpenTelemetry tracing...")

    async with cache._tracer.trace_operation("demo_operation", "demo_key"):
        await cache.set("traced_operation", "traced_value", ttl=60)
        value = await cache.get("traced_operation")
        print(f"✓ Traced operation completed: {value}")
        print("  - Check your tracing backend for spans!")

    # 8. Demonstrate stale-if-error
    print("\n8. Testing stale-if-error fallback...")

    # Store some data
    await cache.set("error_test", "backup_value", ttl=60)

    # Simulate a function that will fail
    async def failing_function():
        print("   💥 Function failed!")
        raise Exception("Simulated service failure")

    try:
        # This should return the stale value instead of raising an error
        result = await cache.fetch_or_set("error_test", failing_function, ttl=60)
        print(f"✓ Stale-if-error fallback: {result}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

    # 9. Test HTTP middleware (setup only - would need actual FastAPI app)
    print("\n9. HTTP Middleware setup example...")

    app = FastAPI(title="YokedCache Demo API")

    # Add caching middleware
    app.add_middleware(  # type: ignore[call-arg]
        HTTPCacheMiddleware,
        cache=cache,
        cache_ttl=300,
        cache_key_prefix="api",
        include_paths=["/api/*"],
        exclude_paths=["/admin/*", "/health"],
    )

    @app.get("/api/data/{item_id}")
    async def get_data(item_id: int):
        """Example endpoint that will be automatically cached."""
        return {
            "id": item_id,
            "data": f"Data for item {item_id}",
            "timestamp": time.time(),
        }

    print("✓ FastAPI app configured with caching middleware")
    print("  - Automatic ETag/Cache-Control headers")
    print("  - 304 Not Modified responses for unchanged data")
    print("  - Run with: uvicorn advanced_features_demo:app")

    # Cleanup
    print("\n🧹 Cleaning up...")
    await cache.disconnect()
    await disk_backend.disconnect()
    await sqlite_backend.disconnect()

    print("\n🎉 Advanced features demo completed!")
    print("\nKey takeaways:")
    print("- Single-flight prevents stampede conditions")
    print("- SWR provides fast responses with background updates")
    print("- Prefix routing enables data sharding across backends")
    print("- OpenTelemetry integration provides observability")
    print("- HTTP middleware adds caching to FastAPI with zero code changes")


if __name__ == "__main__":
    # Run the async demo
    asyncio.run(main())
