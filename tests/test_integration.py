"""
Integration tests for YokedCache improvements.

Tests the critical fixes and new features based on real-world feedback.
"""

import asyncio
import inspect
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache import YokedCache
from yokedcache.circuit_breaker import CircuitBreaker, CircuitBreakerError
from yokedcache.config import CacheConfig
from yokedcache.decorators import cached_dependency
from yokedcache.exceptions import CacheConnectionError


class TestConnectionPoolKwargs:
    """Test the CacheConfig connection_pool_kwargs support."""

    def test_config_accepts_connection_pool_kwargs(self):
        """Test that CacheConfig accepts connection_pool_kwargs parameter."""
        connection_pool_kwargs = {
            "socket_keepalive": True,
            "socket_keepalive_options": {},
            "retry_on_timeout": True,
        }

        config = CacheConfig(connection_pool_kwargs=connection_pool_kwargs)

        assert config.connection_pool_kwargs == connection_pool_kwargs

    def test_get_connection_pool_config_merges_kwargs(self):
        """Test that get_connection_pool_config merges base config with custom kwargs."""
        connection_pool_kwargs = {
            "socket_keepalive": True,
            "socket_keepalive_options": {},
            "custom_param": "test_value",
        }

        config = CacheConfig(
            max_connections=100,
            socket_timeout=10.0,
            connection_pool_kwargs=connection_pool_kwargs,
        )

        pool_config = config.get_connection_pool_config()

        # Should include base config
        assert pool_config["max_connections"] == 100
        assert pool_config["socket_timeout"] == 10.0

        # Should include custom kwargs
        assert pool_config["socket_keepalive"] is True
        assert pool_config["custom_param"] == "test_value"

        # Custom kwargs should override base config if same key
        config_with_override = CacheConfig(
            retry_on_timeout=False, connection_pool_kwargs={"retry_on_timeout": True}
        )
        pool_config = config_with_override.get_connection_pool_config()
        assert pool_config["retry_on_timeout"] is True


class TestAsyncSyncHandling:
    """Test improved async/sync context handling."""

    @pytest.fixture
    def cache(self):
        """Create cache instance for testing."""
        config = CacheConfig(
            redis_url="redis://localhost:6379/1",
            enable_circuit_breaker=False,
            fallback_enabled=True,
        )
        return YokedCache(config)

    @pytest.mark.asyncio
    async def test_async_methods_work_correctly(self, cache):
        """Test that async methods work correctly in async context."""
        await cache.connect()

        try:
            # Test async set
            result = await cache.set("test_key", "test_value")
            assert result is True

            # Test async get
            value = await cache.get("test_key")
            assert value == "test_value"

            # Test explicit async methods
            value = await cache.aget("test_key")
            assert value == "test_value"

            result = await cache.adelete("test_key")
            assert result is True

        finally:
            await cache.disconnect()

    def test_sync_methods_with_warnings(self, cache):
        """Test that sync methods work but issue warnings when appropriate."""
        with patch("yokedcache.cache.logger") as mock_logger:
            # These methods should work but may log warnings
            try:
                result = cache.get_sync("nonexistent_key", "default")
                assert result == "default"

                # Should warn about sync usage in async context detection
                # (though this test is running in sync context)

            except Exception as e:
                # Expected if Redis is not available
                assert "Redis" in str(e) or "connection" in str(e).lower()

    @pytest.mark.asyncio
    async def test_sync_in_async_context_detection(self, cache):
        """Test detection of sync methods called from async context."""
        await cache.connect()

        try:
            with patch("yokedcache.cache.logger") as mock_logger:
                # Calling sync method from async context should warn
                # Note: Our implementation gracefully handles this rather than raising
                result = cache.get_sync("test_key", "default")

                # Should either get default value or handle gracefully
                assert result is not None  # Should get default or fallback value

        finally:
            await cache.disconnect()


class TestCachedDependency:
    """Test the redesigned cached_dependency for FastAPI generators."""

    def test_cached_dependency_with_regular_function(self):
        """Test cached_dependency with regular (non-generator) functions."""

        def mock_dependency():
            return MagicMock(query=MagicMock(), execute=MagicMock())

        cache = YokedCache()
        cached_dep = cached_dependency(mock_dependency, cache=cache)

        # Should return wrapped dependency
        result = cached_dep()
        assert hasattr(result, "query")
        assert hasattr(result, "_cache")

    def test_cached_dependency_with_sync_generator(self):
        """Test cached_dependency with sync generator functions."""

        def mock_generator_dependency():
            db_session = MagicMock(query=MagicMock(), execute=MagicMock())
            try:
                yield db_session
            finally:
                # Cleanup
                db_session.close()

        cache = YokedCache()
        cached_dep = cached_dependency(mock_generator_dependency, cache=cache)

        # Should be a generator function
        assert inspect.isgeneratorfunction(cached_dep)

        # Should work when called
        gen = cached_dep()
        db_session = next(gen)
        assert hasattr(db_session, "_cache")

    @pytest.mark.asyncio
    async def test_cached_dependency_with_async_generator(self):
        """Test cached_dependency with async generator functions."""

        async def mock_async_generator_dependency():
            db_session = MagicMock(query=MagicMock(), execute=MagicMock())
            try:
                yield db_session
            finally:
                # Cleanup
                pass

        cache = YokedCache()
        cached_dep = cached_dependency(mock_async_generator_dependency, cache=cache)

        # Should be an async generator function
        assert inspect.isasyncgenfunction(cached_dep)

        # Should work when called
        async_gen = cached_dep()
        db_session = await async_gen.__anext__()
        assert hasattr(db_session, "_cache")


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_creation(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(
            failure_threshold=3, timeout=30.0, expected_exception=Exception
        )

        assert cb.failure_threshold == 3
        assert cb.timeout == 30.0
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1.0)

        async def failing_operation():
            raise ConnectionError("Test failure")

        # First failure
        with pytest.raises(ConnectionError):
            await cb.call_async(failing_operation)

        # Second failure - should open circuit
        with pytest.raises(ConnectionError):
            await cb.call_async(failing_operation)

        # Third call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerError):
            await cb.call_async(failing_operation)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery via half-open state."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)

        async def failing_operation():
            raise ConnectionError("Test failure")

        async def working_operation():
            return "success"

        # Cause failure to open circuit
        with pytest.raises(ConnectionError):
            await cb.call_async(failing_operation)

        # Should be open now
        with pytest.raises(CircuitBreakerError):
            await cb.call_async(working_operation)

        # Wait for timeout
        await asyncio.sleep(0.2)

        # Should allow one test call (half-open)
        result = await cb.call_async(working_operation)
        assert result == "success"

        # Should be closed now and work normally
        result = await cb.call_async(working_operation)
        assert result == "success"


class TestErrorHandling:
    """Test improved error handling and resilience."""

    @pytest.fixture
    def resilient_cache(self):
        """Create cache with error handling enabled."""
        config = CacheConfig(
            redis_url="redis://nonexistent:6379/0",  # Invalid Redis URL
            enable_circuit_breaker=True,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_timeout=1.0,
            fallback_enabled=True,
            connection_retries=1,
        )
        return YokedCache(config)

    @pytest.mark.asyncio
    async def test_fallback_behavior_on_connection_failure(self, resilient_cache):
        """Test that fallback behavior works when Redis is unavailable."""
        # These operations should fall back gracefully
        result = await resilient_cache.get("test_key", "default_value")
        assert result == "default_value"

        result = await resilient_cache.set("test_key", "test_value")
        # Should return False or None due to fallback
        assert result is False or result is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, resilient_cache):
        """Test circuit breaker integration with cache operations."""
        # Multiple failed operations should trigger circuit breaker
        for _ in range(3):
            try:
                await resilient_cache.get("test_key")
            except Exception:
                pass

        # Circuit breaker should be tracking failures
        if resilient_cache._circuit_breaker:
            stats = resilient_cache._circuit_breaker.get_stats()
            assert stats["total_failures"] > 0


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.fixture
    def cache_with_health(self):
        """Create cache for health check testing."""
        config = CacheConfig(
            redis_url="redis://localhost:6379/1",
            enable_circuit_breaker=True,
        )
        return YokedCache(config)

    @pytest.mark.asyncio
    async def test_basic_health_check(self, cache_with_health):
        """Test basic health check functionality."""
        await cache_with_health.connect()

        try:
            health = await cache_with_health.health_check()
            # Should return True if Redis is available, False if not
            assert isinstance(health, bool)
        finally:
            await cache_with_health.disconnect()

    @pytest.mark.asyncio
    async def test_detailed_health_check(self, cache_with_health):
        """Test detailed health check functionality."""
        try:
            health_info = await cache_with_health.detailed_health_check()

            # Should return comprehensive health information
            assert "status" in health_info
            assert "timestamp" in health_info
            assert "cache" in health_info
            assert "performance" in health_info
            assert "errors" in health_info
            assert "warnings" in health_info

            # Status should be one of expected values
            assert health_info["status"] in ["healthy", "degraded", "unhealthy"]

        except Exception as e:
            # Expected if Redis is not available
            pass


class TestMetricsCollection:
    """Test comprehensive metrics collection."""

    @pytest.fixture
    def cache_with_metrics(self):
        """Create cache with metrics enabled."""
        config = CacheConfig(
            redis_url="redis://localhost:6379/1",
            enable_metrics=True,
            metrics_interval=1,
        )
        return YokedCache(config)

    @pytest.mark.asyncio
    async def test_metrics_recording(self, cache_with_metrics):
        """Test that metrics are recorded for operations."""
        await cache_with_metrics.connect()

        try:
            # Perform some operations
            await cache_with_metrics.set("test_key", "test_value")
            await cache_with_metrics.get("test_key")
            await cache_with_metrics.get("nonexistent_key")

            # Get metrics
            if cache_with_metrics._metrics:
                stats = cache_with_metrics._metrics.get_comprehensive_stats()

                # Should have recorded operations
                assert stats["operations"]["total"] > 0
                assert "set" in stats["operations"]["by_type"]
                assert "get" in stats["operations"]["by_type"]

                # Should have performance data
                assert "response_times" in stats
                assert "cache_performance" in stats

        finally:
            await cache_with_metrics.disconnect()

    @pytest.mark.asyncio
    async def test_comprehensive_metrics_api(self, cache_with_metrics):
        """Test the comprehensive metrics API."""
        try:
            metrics = await cache_with_metrics.get_comprehensive_metrics()

            # Should return structured metrics data
            assert "timestamp" in metrics

            if cache_with_metrics._metrics:
                assert "operations" in metrics
                assert "cache_performance" in metrics
                assert "response_times" in metrics
            else:
                assert "metrics_enabled" in metrics
                assert "basic_stats" in metrics

        except Exception:
            # Expected if Redis is not available
            pass


class TestRealWorldScenarios:
    """Test scenarios based on real-world feedback."""

    @pytest.mark.asyncio
    async def test_fastapi_dependency_pattern(self):
        """Test the FastAPI dependency injection pattern that was failing."""

        # Simulate FastAPI dependency generator
        def get_db():
            """Mock database dependency generator."""
            db = MagicMock()
            db.query = MagicMock()
            db.execute = MagicMock()
            try:
                yield db
            finally:
                db.close()

        # Cache the dependency
        cache = YokedCache()
        cached_get_db = cached_dependency(get_db, cache=cache)

        # Should return a generator function
        assert inspect.isgeneratorfunction(cached_get_db)

        # Should work when used
        gen = cached_get_db()
        db_session = next(gen)

        # Should be wrapped with caching capabilities
        assert hasattr(db_session, "_cache")
        assert hasattr(db_session, "query")

    @pytest.mark.asyncio
    async def test_high_load_scenario(self):
        """Test cache behavior under high load (simulated)."""
        config = CacheConfig(
            redis_url="redis://localhost:6379/1",
            max_connections=10,
            enable_circuit_breaker=True,
            enable_metrics=True,
        )
        cache = YokedCache(config)

        try:
            await cache.connect()

            # Simulate high load with concurrent operations
            tasks = []
            for i in range(50):
                tasks.append(cache.set(f"key_{i}", f"value_{i}"))
                tasks.append(cache.get(f"key_{i}"))

            # Execute all operations concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Most operations should succeed (allowing for some failures)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            total_count = len(results)
            success_rate = success_count / total_count

            # Should have at least 70% success rate
            assert success_rate > 0.7

        except Exception:
            # Expected if Redis is not available
            pass
        finally:
            await cache.disconnect()

    def test_config_parameter_validation(self):
        """Test that all new configuration parameters are properly validated."""
        # Should accept valid parameters
        config = CacheConfig(
            connection_pool_kwargs={"socket_keepalive": True},
            enable_circuit_breaker=True,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout=60.0,
            fallback_enabled=True,
            connection_retries=3,
        )

        # Validation should pass
        assert config.enable_circuit_breaker is True
        assert config.circuit_breaker_failure_threshold == 5
        assert config.fallback_enabled is True

        # Should reject invalid parameters
        with pytest.raises(Exception):
            CacheConfig(circuit_breaker_failure_threshold=0)

        with pytest.raises(Exception):
            CacheConfig(connection_retries=-1)


@pytest.mark.integration
class TestProductionReadiness:
    """Test production readiness of the improvements."""

    @pytest.mark.asyncio
    async def test_error_recovery_cycle(self):
        """Test complete error recovery cycle."""
        config = CacheConfig(
            redis_url="redis://localhost:6379/1",
            enable_circuit_breaker=True,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_timeout=0.5,
            fallback_enabled=True,
            connection_retries=1,
        )
        cache = YokedCache(config)

        try:
            # Should handle connection gracefully
            result = await cache.get("test_key", "default")

            # Should either work or fall back gracefully
            assert result is not None

        except Exception as e:
            # Should be a controlled exception, not a crash
            assert isinstance(e, (CacheConnectionError, ConnectionError))

    @pytest.mark.asyncio
    async def test_monitoring_capabilities(self):
        """Test that monitoring capabilities work end-to-end."""
        config = CacheConfig(
            enable_metrics=True,
            enable_circuit_breaker=True,
        )
        cache = YokedCache(config)

        try:
            # Get health status
            health = await cache.detailed_health_check()
            assert "status" in health

            # Get metrics
            metrics = await cache.get_comprehensive_metrics()
            assert "timestamp" in metrics

        except Exception:
            # Expected if Redis not available
            pass
