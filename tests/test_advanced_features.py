"""Tests for advanced caching features: routing, SWR, tracing."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import with fallback for missing modules during testing
try:
    from yokedcache.cache import YokedCache
    from yokedcache.config import CacheConfig
except ImportError:
    pytest.skip("Core modules not available", allow_module_level=True)

try:
    from yokedcache.routing import PrefixRouter
except ImportError:
    PrefixRouter = None  # type: ignore[misc]

try:
    from yokedcache.swr import SWRScheduler
except ImportError:
    SWRScheduler = None  # type: ignore[misc]

try:
    from yokedcache.tracing import CacheTracer, initialize_tracing
except ImportError:
    CacheTracer = None  # type: ignore[misc]
    initialize_tracing = None


@pytest.mark.skipif(PrefixRouter is None, reason="PrefixRouter not available")
class TestPrefixRouter:
    """Test prefix-based routing and sharding."""

    def test_router_initialization(self):
        """Test router can be initialized with a default backend."""
        mock_backend = MagicMock()
        router = PrefixRouter(mock_backend)

        assert router.default_backend == mock_backend
        assert len(router.prefix_map) == 0

    def test_add_route(self):
        """Test adding prefix routes."""
        mock_default = MagicMock()
        mock_backend = MagicMock()
        router = PrefixRouter(mock_default)

        router.add_route("user:", mock_backend)
        assert "user:" in router.prefix_map
        assert router.prefix_map["user:"] == mock_backend

    def test_remove_route(self):
        """Test removing prefix routes."""
        mock_default = MagicMock()
        mock_backend = MagicMock()
        router = PrefixRouter(mock_default)

        router.add_route("user:", mock_backend)
        result = router.remove_route("user:")
        assert result is True
        assert "user:" not in router.prefix_map

        # Test removing non-existent route
        result = router.remove_route("missing:")
        assert result is False

    def test_get_backend_with_route(self):
        """Test getting backend for keys with matching prefixes."""
        mock_default = MagicMock()
        mock_user_backend = MagicMock()
        mock_session_backend = MagicMock()
        router = PrefixRouter(mock_default)

        router.add_route("user:", mock_user_backend)
        router.add_route("session:", mock_session_backend)

        # Test matching prefixes
        assert router.get_backend("user:123") == mock_user_backend
        assert router.get_backend("session:abc") == mock_session_backend

        # Test default backend
        assert router.get_backend("other:key") == mock_default
        assert router.get_backend("no_prefix") == mock_default

    def test_get_backend_longest_match(self):
        """Test that longest prefix match wins."""
        mock_default = MagicMock()
        mock_user_backend = MagicMock()
        mock_admin_backend = MagicMock()
        router = PrefixRouter(mock_default)

        router.add_route("user:", mock_user_backend)
        router.add_route("user:admin:", mock_admin_backend)

        # Longer prefix should win
        assert router.get_backend("user:admin:123") == mock_admin_backend
        assert router.get_backend("user:regular:123") == mock_user_backend

    @pytest.mark.asyncio
    async def test_router_operations(self):
        """Test router delegates operations correctly."""
        mock_default = AsyncMock()
        mock_backend = AsyncMock()
        router = PrefixRouter(mock_default)
        router.add_route("test:", mock_backend)

        # Test delegated operations
        await router.get("test:key", "default")
        mock_backend.get.assert_called_once_with("test:key", "default")

        await router.set("test:key", "value", 60, {"tag1"})
        mock_backend.set.assert_called_once_with("test:key", "value", 60, {"tag1"})

        await router.delete("test:key")
        mock_backend.delete.assert_called_once_with("test:key")

        await router.exists("test:key")
        mock_backend.exists.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_connect_all_backends(self):
        """Test connecting all registered backends."""
        mock_default = AsyncMock()
        mock_backend1 = AsyncMock()
        mock_backend2 = AsyncMock()

        router = PrefixRouter(mock_default)
        router.add_route("test1:", mock_backend1)
        router.add_route("test2:", mock_backend2)

        await router.connect_all()

        mock_default.connect.assert_called_once()
        mock_backend1.connect.assert_called_once()
        mock_backend2.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_all_backends(self):
        """Test disconnecting all registered backends."""
        mock_default = AsyncMock()
        mock_backend1 = AsyncMock()
        mock_backend2 = AsyncMock()

        router = PrefixRouter(mock_default)
        router.add_route("test1:", mock_backend1)
        router.add_route("test2:", mock_backend2)

        await router.disconnect_all()

        mock_default.disconnect.assert_called_once()
        mock_backend1.disconnect.assert_called_once()
        mock_backend2.disconnect.assert_called_once()


@pytest.mark.skipif(SWRScheduler is None, reason="SWRScheduler not available")
class TestSWRScheduler:
    """Test stale-while-revalidate scheduling."""

    @pytest.mark.asyncio
    async def test_scheduler_initialization(self):
        """Test scheduler initializes correctly."""
        mock_cache = MagicMock()
        scheduler = SWRScheduler(mock_cache)

        assert hasattr(scheduler, "_refresh_tasks")
        assert len(scheduler._refresh_tasks) == 0
        assert scheduler._cleanup_task is None

    @pytest.mark.asyncio
    async def test_schedule_refresh(self):
        """Test scheduling background refresh."""
        mock_cache = AsyncMock()
        mock_fetcher = AsyncMock(return_value="new_value")

        scheduler = SWRScheduler(mock_cache)
        scheduler.start()

        # Schedule a refresh
        scheduler.schedule_refresh("test_key", mock_fetcher, ttl=60)

        # Should have a task scheduled
        assert "test_key" in scheduler._refresh_tasks

        # Clean up
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_refresh_execution(self):
        """Test that scheduled refresh actually executes."""
        mock_cache = AsyncMock()
        mock_fetcher = AsyncMock(return_value="refreshed_value")

        scheduler = SWRScheduler(mock_cache)
        scheduler.start()

        # Schedule refresh with short delay
        scheduler.schedule_refresh("test_key", mock_fetcher, ttl=60)

        # Wait for refresh to execute
        await asyncio.sleep(2)

        # Verify fetcher was called and cache was updated
        mock_fetcher.assert_called_once()
        mock_cache.set.assert_called_once_with("test_key", "refreshed_value", 60)

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self):
        """Test cleanup of completed refresh tasks."""
        mock_cache = AsyncMock()
        scheduler = SWRScheduler(mock_cache)
        scheduler.start()

        # Add a mock completed task
        completed_task = AsyncMock()
        completed_task.done.return_value = True
        scheduler._refresh_tasks["test_key"] = completed_task

        # Wait for cleanup
        await asyncio.sleep(1.1)  # Cleanup runs every second

        # Task should be removed
        assert "test_key" not in scheduler._refresh_tasks

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self):
        """Test stopping the scheduler cancels all tasks."""
        mock_cache = AsyncMock()
        mock_fetcher = AsyncMock()

        scheduler = SWRScheduler(mock_cache)
        scheduler.start()

        # Schedule some refreshes
        scheduler.schedule_refresh("key1", mock_fetcher, ttl=60)
        scheduler.schedule_refresh("key2", mock_fetcher, ttl=60)

        # Stop scheduler
        await scheduler.stop()

        # All tasks should be cancelled
        assert len(scheduler._refresh_tasks) == 0
        assert scheduler._cleanup_task is None or scheduler._cleanup_task.cancelled()


@pytest.mark.skipif(CacheTracer is None, reason="CacheTracer not available")
class TestCacheTracer:
    """Test OpenTelemetry integration."""

    def test_tracer_initialization(self):
        """Test tracer initializes correctly."""
        tracer = CacheTracer("test-service")

        assert tracer.service_name == "test-service"
        assert hasattr(tracer, "_tracer")

    @patch("yokedcache.tracing.trace")
    def test_trace_operation_context_manager(self, mock_trace_module):
        """Test tracing context manager."""
        mock_span = MagicMock()
        mock_trace_module.get_tracer.return_value.start_span.return_value.__enter__.return_value = (
            mock_span
        )

        tracer = CacheTracer("test-service")

        # Since trace_operation is async, test that it can be created
        context_manager = tracer.trace_operation("get", "test_key")
        assert context_manager is not None

    def test_trace_hit(self):
        """Test recording cache hit metrics."""
        tracer = CacheTracer("test-service")

        # Should not raise any errors
        tracer.trace_hit("test_key")

    def test_trace_miss(self):
        """Test recording cache miss metrics."""
        tracer = CacheTracer("test-service")

        # Should not raise any errors
        tracer.trace_miss("test_key")

    def test_add_event(self):
        """Test adding events to spans."""
        tracer = CacheTracer("test-service")

        # Should not raise any errors
        tracer.add_event("cache.operation", key="test_key")

    @patch("yokedcache.tracing.logger")
    def test_initialize_global_tracing(self, mock_logger):
        """Test global tracing initialization."""
        if initialize_tracing:
            tracer = initialize_tracing("test-app", enabled=True, sample_rate=1.0)
            assert tracer is not None
            assert tracer.service_name == "test-app"


@pytest.mark.asyncio
class TestCacheIntegration:
    """Test integration of advanced features with main cache."""

    async def test_cache_with_prefix_routing(self):
        """Test cache operations with prefix routing enabled."""
        config = CacheConfig(redis_url="redis://localhost:6379")

        # Mock the connection for testing
        with patch("yokedcache.cache.redis.Redis.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            cache = YokedCache(config)
            await cache.connect()

            # Setup prefix routing
            cache.setup_prefix_routing()

            # Add a mock backend for user keys
            mock_user_backend = AsyncMock()
            cache.add_backend_route("user:", mock_user_backend)

            # Test that user keys go to the special backend
            await cache.get("user:123")
            mock_user_backend.get.assert_called_once_with("user:123", None)

            # Test that other keys go to default backend
            await cache.get("other:key")
            # Should have called Redis client through the wrapper

            await cache.disconnect()

    async def test_cache_with_swr_scheduling(self):
        """Test cache with SWR background refresh."""
        config = CacheConfig(
            redis_url="redis://localhost:6379", enable_stale_while_revalidate=True
        )

        with patch("yokedcache.cache.redis.Redis.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            cache = YokedCache(config)
            await cache.connect()

            # SWR scheduler should be initialized
            assert cache._swr_scheduler is not None

            # Test fetch_or_set with SWR
            mock_fetcher = AsyncMock(return_value="fresh_value")

            # Mock cache miss first, then hit
            mock_client.get.side_effect = [None, b'{"data": "fresh_value"}']

            result = await cache.fetch_or_set("test_key", mock_fetcher, ttl=60)

            # Should get the fresh value
            assert result == "fresh_value"

            await cache.disconnect()

    async def test_cache_with_tracing(self):
        """Test cache with OpenTelemetry tracing."""
        config = CacheConfig(redis_url="redis://localhost:6379", enable_tracing=True)

        with patch("yokedcache.cache.redis.Redis.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client
            mock_client.get.return_value = b'"test_value"'

            cache = YokedCache(config)
            await cache.connect()

            # Tracer should be initialized
            assert cache._tracer is not None

            # Test traced operation
            result = await cache.get("test_key")

            # Operation should complete successfully
            assert result == "test_value"

            await cache.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])
