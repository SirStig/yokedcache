"""
Comprehensive tests for YokedCache class to increase coverage.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache import CacheConfig, YokedCache
from yokedcache.exceptions import CacheConnectionError, CacheKeyError


class TestYokedCacheInitialization:
    """Test YokedCache initialization and configuration."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        cache = YokedCache(enable_env_overrides=False)
        assert cache.config is not None
        assert cache.config.redis_url == "redis://localhost:6379/0"

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = CacheConfig(
            redis_url="redis://custom:6380/1", enable_env_overrides=False
        )
        cache = YokedCache(config)
        assert cache.config.redis_url == "redis://custom:6380/1"

    def test_init_with_kwargs(self):
        """Test initialization with keyword arguments."""
        cache = YokedCache(redis_url="redis://test:6379/2", default_ttl=300)
        assert cache.config.redis_url == "redis://test:6379/2"
        assert cache.config.default_ttl == 300

    def test_init_with_config_and_kwargs(self):
        """Test initialization with both config and kwargs."""
        config = CacheConfig(redis_url="redis://base:6379/0")
        cache = YokedCache(config, default_ttl=600)
        # kwargs should override config
        assert cache.config.default_ttl == 600

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using cache as async context manager."""
        async with YokedCache() as cache:
            assert cache is not None
            assert hasattr(cache, "config")

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test context manager cleanup."""
        cache = YokedCache()
        with patch.object(cache, "close") as mock_close:
            async with cache:
                pass
            mock_close.assert_called_once()


class TestYokedCacheConnectionHandling:
    """Test Redis connection handling."""

    @pytest.mark.asyncio
    async def test_get_redis_connection(self):
        """Test getting Redis connection."""
        cache = YokedCache()
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            async with cache._get_redis() as redis_conn:
                assert redis_conn == mock_redis

    @pytest.mark.asyncio
    async def test_redis_connection_error(self):
        """Test Redis connection error handling."""
        cache = YokedCache()
        with patch(
            "redis.asyncio.from_url", side_effect=Exception("Connection failed")
        ):
            with pytest.raises(CacheConnectionError):
                async with cache._get_redis():
                    pass

    @pytest.mark.asyncio
    async def test_redis_connection_retry(self):
        """Test Redis connection retry logic."""
        cache = YokedCache()
        cache.config.max_retries = 2

        with patch("redis.asyncio.from_url") as mock_from_url:
            # First call fails, second succeeds
            mock_redis = AsyncMock()
            mock_from_url.side_effect = [Exception("Failed"), mock_redis]

            async with cache._get_redis() as redis_conn:
                assert redis_conn == mock_redis

    @pytest.mark.asyncio
    async def test_close_redis_connection(self):
        """Test closing Redis connection."""
        cache = YokedCache()
        mock_redis = AsyncMock()
        cache._redis = mock_redis

        await cache.close()
        mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_redis_connection_fallback(self):
        """Test closing Redis connection with fallback to close()."""
        cache = YokedCache()
        mock_redis = AsyncMock()
        # Remove aclose method to test fallback
        del mock_redis.aclose
        mock_redis.close = AsyncMock()
        cache._redis = mock_redis

        await cache.close()
        mock_redis.close.assert_called_once()


class TestYokedCacheBasicOperations:
    """Test basic cache operations."""

    @pytest.mark.asyncio
    async def test_set_and_get_basic(self):
        """Test basic set and get operations."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.set.return_value = True
            mock_redis.get.return_value = b'{"data": "test_value"}'

            # Test set
            result = await cache.set("test_key", "test_value")
            assert result is True

            # Test get
            value = await cache.get("test_key")
            assert value == {"data": "test_value"}

    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Test set operation with TTL."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.set.return_value = True

            await cache.set("test_key", "test_value", ttl=300)
            mock_redis.set.assert_called_once()
            args, kwargs = mock_redis.set.call_args
            assert kwargs.get("ex") == 300

    @pytest.mark.asyncio
    async def test_set_with_tags(self):
        """Test set operation with tags."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.set.return_value = True
            mock_redis.sadd.return_value = 1

            await cache.set("test_key", "test_value", tags=["tag1", "tag2"])

            # Should call set for the main key and sadd for tags
            mock_redis.set.assert_called()
            assert mock_redis.sadd.call_count >= 2  # At least 2 tag operations

    @pytest.mark.asyncio
    async def test_get_with_default(self):
        """Test get operation with default value."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.get.return_value = None

            value = await cache.get("nonexistent_key", default="default_value")
            assert value == "default_value"

    @pytest.mark.asyncio
    async def test_delete_operation(self):
        """Test delete operation."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.delete.return_value = 1

            result = await cache.delete("test_key")
            assert result is True
            mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_exists_operation(self):
        """Test exists operation."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.exists.return_value = 1

            result = await cache.exists("test_key")
            assert result is True
            mock_redis.exists.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_flush_operation(self):
        """Test flush operation."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.flushdb.return_value = True

            result = await cache.flush()
            assert result is True
            mock_redis.flushdb.assert_called_once()


class TestYokedCacheErrorHandling:
    """Test error handling in cache operations."""

    @pytest.mark.asyncio
    async def test_get_operation_error(self):
        """Test error handling in get operation."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.get.side_effect = Exception("Redis error")

            with pytest.raises(CacheKeyError):
                await cache.get("test_key")

    @pytest.mark.asyncio
    async def test_set_operation_error(self):
        """Test error handling in set operation."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.set.side_effect = Exception("Redis error")

            result = await cache.set("test_key", "test_value")
            assert result is False  # Should return False on error

    @pytest.mark.asyncio
    async def test_fallback_enabled_on_error(self):
        """Test fallback behavior when enabled."""
        config = CacheConfig(fallback_enabled=True)
        cache = YokedCache(config)

        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_get_redis.side_effect = Exception("Connection failed")

            # Should return default value instead of raising
            value = await cache.get("test_key", default="fallback")
            assert value == "fallback"

    @pytest.mark.asyncio
    async def test_fallback_disabled_on_error(self):
        """Test behavior when fallback is disabled."""
        config = CacheConfig(fallback_enabled=False)
        cache = YokedCache(config)

        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_get_redis.side_effect = Exception("Connection failed")

            # Should raise exception
            with pytest.raises(CacheConnectionError):
                await cache.get("test_key")


class TestYokedCacheSyncMethods:
    """Test synchronous wrapper methods."""

    def test_get_sync_basic(self):
        """Test synchronous get method."""
        cache = YokedCache()

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = "test_value"

            result = cache.get_sync("test_key")
            assert result == "test_value"
            mock_run.assert_called_once()

    def test_set_sync_basic(self):
        """Test synchronous set method."""
        cache = YokedCache()

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = True

            result = cache.set_sync("test_key", "test_value")
            assert result is True
            mock_run.assert_called_once()

    def test_delete_sync_basic(self):
        """Test synchronous delete method."""
        cache = YokedCache()

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = True

            result = cache.delete_sync("test_key")
            assert result is True
            mock_run.assert_called_once()

    def test_exists_sync_basic(self):
        """Test synchronous exists method."""
        cache = YokedCache()

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = True

            result = cache.exists_sync("test_key")
            assert result is True
            mock_run.assert_called_once()

    def test_sync_method_runtime_error(self):
        """Test sync method handling of runtime error."""
        cache = YokedCache()
        cache.config.fallback_enabled = True

        with patch(
            "asyncio.run",
            side_effect=RuntimeError("cannot be called from a running event loop"),
        ):
            result = cache.get_sync("test_key", default="fallback")
            assert result == "fallback"

    def test_sync_method_runtime_error_no_fallback(self):
        """Test sync method handling of runtime error without fallback."""
        cache = YokedCache()
        cache.config.fallback_enabled = False

        with patch(
            "asyncio.run",
            side_effect=RuntimeError("cannot be called from a running event loop"),
        ):
            with pytest.raises(RuntimeError):
                cache.get_sync("test_key")


class TestYokedCacheAdvancedFeatures:
    """Test advanced cache features."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting cache statistics."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.info.return_value = {
                "used_memory": 1024,
                "connected_clients": 5,
                "total_commands_processed": 100,
            }
            mock_redis.dbsize.return_value = 10

            stats = await cache.get_stats()
            assert stats is not None
            assert hasattr(stats, "memory_usage")

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.ping.return_value = True

            is_healthy = await cache.health()
            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_ping(self):
        """Test ping operation."""
        cache = YokedCache()
        with patch.object(cache, "_get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value.__aenter__.return_value = mock_redis
            mock_redis.ping.return_value = True

            result = await cache.ping()
            assert result is True
