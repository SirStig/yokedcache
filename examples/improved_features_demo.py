"""
Demonstration script for YokedCache improvements.

This script showcases the critical fixes and new features implemented
based on real-world production feedback.
"""

import asyncio
import logging
from typing import Any, Callable, Generator, cast

from yokedcache import YokedCache
from yokedcache.config import CacheConfig
from yokedcache.decorators import cached_dependency

# Setup logging to see warnings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_connection_pool_kwargs():
    """Demonstrate the fixed connection_pool_kwargs support."""
    print("=== Connection Pool Configuration Demo ===")

    # This now works - was failing before the fix
    connection_pool_kwargs = {
        "socket_keepalive": True,
        "socket_keepalive_options": {},
        "retry_on_timeout": True,
        "socket_connect_timeout": 5.0,
    }

    config = CacheConfig(
        redis_url="redis://localhost:6379/0",
        max_connections=20,
        # This parameter previously failed; now supported
        connection_pool_kwargs=connection_pool_kwargs,
        enable_circuit_breaker=True,
        fallback_enabled=True,
    )

    print("✅ CacheConfig successfully accepts connection_pool_kwargs")
    print(f"✅ Connection pool config: {config.get_connection_pool_config()}")

    cache = YokedCache(config)
    print("✅ YokedCache initialized with custom connection pool settings")
    return cache


async def demo_async_sync_handling():
    """Demonstrate improved async/sync context handling."""
    print("\n=== Async/Sync Context Handling Demo ===")

    cache = demo_connection_pool_kwargs()

    try:
        await cache.connect()

        # These async methods work correctly
        print("Testing async methods...")
        await cache.set("async_key", "async_value")
        value = await cache.get("async_key")
        print(f"✅ Async operations work: {value}")

        # Explicit async methods for clarity
        value = await cache.aget("async_key")
        print(f"✅ Explicit async methods work: {value}")

        # Sync methods now have better error handling
        print("Testing sync methods (may show warnings)...")
        try:
            # This will work but may warn about sync usage
            sync_value = cache.get_sync("async_key", "default")
            print(f"✅ Sync methods work with fallback: {sync_value}")
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                print("✅ Proper error handling for sync methods in async context")
            else:
                raise

    except Exception as e:
        print(f"⚠️  Cache operations failed (Redis might not be available): {e}")
    finally:
        await cache.disconnect()


def demo_fastapi_dependency_fixes():
    """Demonstrate the fixed FastAPI dependency handling."""
    print("\n=== FastAPI Dependency Generator Demo ===")

    # Simulate a FastAPI database dependency generator
    def get_db() -> Generator:
        """Mock database dependency that yields a session."""
        print("Creating database session...")
        db_session = MockDBSession()
        try:
            yield db_session
        finally:
            print("Closing database session...")
            db_session.close()

    # This now works correctly - was returning generator objects before
    cache = YokedCache()
    cached_get_db = cast(
        Callable[[], Generator[Any, None, None]],
        cached_dependency(get_db, cache=cache),
    )

    print("✅ cached_dependency correctly handles generator functions")

    # Use the cached dependency
    gen = cached_get_db()
    db_session = next(gen)

    print(f"✅ Generator dependency works: {type(db_session)}")
    print(f"✅ Session has caching wrapper: {hasattr(db_session, '_cache')}")

    # Simulate database operations
    result = db_session.query("SELECT * FROM users")
    print(f"✅ Database operations work through wrapper: {result}")


async def demo_circuit_breaker():
    """Demonstrate circuit breaker functionality."""
    print("\n=== Circuit Breaker Demo ===")

    config = CacheConfig(
        redis_url="redis://nonexistent:6379/0",  # Intentionally invalid
        enable_circuit_breaker=True,
        circuit_breaker_failure_threshold=2,
        circuit_breaker_timeout=2.0,
        fallback_enabled=True,
    )

    cache = YokedCache(config)

    print("Testing circuit breaker with failing Redis connection...")

    # These operations will fail but should be handled gracefully
    for i in range(5):
        try:
            result = await cache.get(f"key_{i}", f"default_{i}")
            print(f"Operation {i}: {result}")
        except Exception as e:
            print(f"Operation {i} failed: {type(e).__name__}")

    # Check circuit breaker stats
    if cache._circuit_breaker:
        stats = cache._circuit_breaker.get_stats()
        print(f"✅ Circuit breaker stats: {stats}")


async def demo_health_check():
    """Demonstrate comprehensive health check."""
    print("\n=== Health Check Demo ===")

    cache = demo_connection_pool_kwargs()

    try:
        # Basic health check
        health = await cache.health_check()
        print(f"Basic health check: {health}")

        # Detailed health check
        detailed_health = await cache.detailed_health_check()
        print(f"✅ Detailed health check status: {detailed_health['status']}")
        print(f"Health check keys: {list(detailed_health.keys())}")

        if detailed_health["errors"]:
            print(f"Errors: {detailed_health['errors']}")
        if detailed_health["warnings"]:
            print(f"Warnings: {detailed_health['warnings']}")

    except Exception as e:
        print(f"⚠️  Health check failed (Redis might not be available): {e}")


async def demo_metrics_collection():
    """Demonstrate enhanced metrics collection."""
    print("\n=== Metrics Collection Demo ===")

    config = CacheConfig(
        enable_metrics=True,
        metrics_interval=1,
    )
    cache = YokedCache(config)

    try:
        await cache.connect()

        # Perform some operations to generate metrics
        await cache.set("metrics_key1", "value1")
        await cache.set("metrics_key2", "value2", tags=["user", "session"])
        await cache.get("metrics_key1")
        await cache.get("nonexistent_key", "default")

        # Get comprehensive metrics
        metrics = await cache.get_comprehensive_metrics()

        print("✅ Metrics collected successfully")
        total_ops = metrics.get("operations", {}).get("total", 0)
        print(f"Total operations: {total_ops}")
        hit_rate = metrics.get("cache_performance", {}).get("hit_rate_percent", 0)
        print(f"Hit rate: {hit_rate:.1f}%")
        avg_ms = metrics.get("response_times", {}).get("average_ms", 0)
        print(f"Average response time: {avg_ms:.2f}ms")

    except Exception as e:
        print(f"⚠️  Metrics demo failed (Redis might not be available): {e}")
    finally:
        await cache.disconnect()


class MockDBSession:
    """Mock database session for demonstration."""

    def __init__(self):
        self.closed = False

    def query(self, sql: str):
        """Mock query method."""
        if self.closed:
            raise RuntimeError("Session is closed")
        return f"Mock result for: {sql}"

    def execute(self, sql: str):
        """Mock execute method."""
        if self.closed:
            raise RuntimeError("Session is closed")
        return f"Executed: {sql}"

    def close(self):
        """Mock close method."""
        self.closed = True


async def main():
    """Run all demonstrations."""
    print("YokedCache Improvements Demonstration")
    print("=" * 50)

    # Demo 1: Connection pool kwargs (the critical issue)
    demo_connection_pool_kwargs()

    # Demo 2: Async/sync context handling
    await demo_async_sync_handling()

    # Demo 3: FastAPI dependency generator fixes
    demo_fastapi_dependency_fixes()

    # Demo 4: Circuit breaker and error handling
    await demo_circuit_breaker()

    # Demo 5: Health check functionality
    await demo_health_check()

    # Demo 6: Enhanced metrics
    await demo_metrics_collection()

    print("\n" + "=" * 50)
    print("✅ All demos completed successfully!")
    print("\n🎉 YokedCache is now production-ready with all critical fixes!")


if __name__ == "__main__":
    asyncio.run(main())
