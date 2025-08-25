"""
Tests for the core YokedCache functionality.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from yokedcache import CacheConfig, YokedCache
from yokedcache.exceptions import CacheConnectionError
from yokedcache.models import SerializationMethod


class TestYokedCache:
    """Test cases for YokedCache class."""

    @pytest.mark.asyncio
    async def test_basic_get_set(self, cache):
        """Test basic get and set operations."""
        key = "test_key"
        value = {"message": "Hello World", "number": 42}

        # Set value
        result = await cache.set(key, value, ttl=60)
        assert result is True

        # Get value
        retrieved = await cache.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache):
        """Test getting a non-existent key returns default."""
        result = await cache.get("nonexistent_key", default="not_found")
        assert result == "not_found"

    @pytest.mark.asyncio
    async def test_delete_key(self, cache):
        """Test deleting a cache key."""
        key = "test_delete"
        value = "to_be_deleted"

        # Set and verify
        await cache.set(key, value)
        assert await cache.get(key) == value

        # Delete and verify
        deleted = await cache.delete(key)
        assert deleted is True

        # Verify it's gone
        assert await cache.get(key) is None

    @pytest.mark.asyncio
    async def test_key_exists(self, cache):
        """Test checking if key exists."""
        key = "existence_test"

        # Initially doesn't exist
        assert await cache.exists(key) is False

        # Set and check
        await cache.set(key, "exists")
        assert await cache.exists(key) is True

        # Delete and check
        await cache.delete(key)
        assert await cache.exists(key) is False

    @pytest.mark.asyncio
    async def test_expire_key(self, cache):
        """Test setting expiration on existing key."""
        key = "expire_test"

        await cache.set(key, "will_expire", ttl=3600)  # 1 hour

        # Set shorter expiration
        result = await cache.expire(key, 1)  # 1 second
        assert result is True

        # Wait and check if expired
        await asyncio.sleep(1.1)
        assert await cache.get(key) is None

    @pytest.mark.asyncio
    async def test_tags_functionality(self, cache):
        """Test tag-based operations."""
        tags = ["user_data", "session"]

        # Set multiple keys with same tags
        await cache.set("user:1", {"name": "Alice"}, tags=tags)
        await cache.set("user:2", {"name": "Bob"}, tags=tags)
        await cache.set("post:1", {"title": "Test"}, tags=["content"])

        # Verify keys exist
        assert await cache.get("user:1") is not None
        assert await cache.get("user:2") is not None
        assert await cache.get("post:1") is not None

        # Invalidate by tags
        deleted_count = await cache.invalidate_tags(tags)
        assert deleted_count == 2

        # Verify tagged keys are gone, untagged remains
        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
        assert await cache.get("post:1") is not None

    @pytest.mark.asyncio
    async def test_pattern_invalidation(self, cache):
        """Test pattern-based invalidation."""
        # Set multiple keys with pattern
        await cache.set("user:1:profile", {"name": "Alice"})
        await cache.set("user:2:profile", {"name": "Bob"})
        await cache.set("user:1:settings", {"theme": "dark"})
        await cache.set("post:1", {"title": "Test"})

        # Invalidate user profile pattern
        deleted_count = await cache.invalidate_pattern("user:*:profile")
        assert deleted_count == 2

        # Verify correct keys were deleted
        assert await cache.get("user:1:profile") is None
        assert await cache.get("user:2:profile") is None
        assert await cache.get("user:1:settings") is not None
        assert await cache.get("post:1") is not None

    @pytest.mark.asyncio
    async def test_stats_tracking(self, cache):
        """Test cache statistics tracking."""
        # Perform some operations
        await cache.set("test1", "value1")
        await cache.set("test2", "value2")

        # Hits
        await cache.get("test1")
        await cache.get("test2")

        # Misses
        await cache.get("nonexistent1")
        await cache.get("nonexistent2")

        # Get stats
        stats = await cache.get_stats()

        assert stats.total_sets >= 2
        assert stats.total_hits >= 2
        assert stats.total_misses >= 2
        assert stats.hit_rate > 0
        assert stats.miss_rate > 0
        assert stats.uptime_seconds > 0

    @pytest.mark.asyncio
    async def test_serialization_methods(self, cache):
        """Test different serialization methods."""
        test_data = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }

        # Test JSON serialization (default)
        await cache.set("json_test", test_data, serialization=SerializationMethod.JSON)
        result = await cache.get("json_test")
        assert result == test_data

        # Test pickle serialization
        await cache.set(
            "pickle_test", test_data, serialization=SerializationMethod.PICKLE
        )
        result = await cache.get("pickle_test")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_fuzzy_search(self, cache):
        """Test fuzzy search functionality."""
        # Set up test data
        await cache.set("user_alice_profile", {"name": "Alice"})
        await cache.set("user_bob_profile", {"name": "Bob"})
        await cache.set("product_apple", {"name": "Apple"})

        # Perform fuzzy search
        results = await cache.fuzzy_search("alice", threshold=70)

        # Should find the alice profile
        assert len(results) > 0
        found = False
        for result in results:
            if "alice" in result.key.lower():
                found = True
                break
        assert found

    @pytest.mark.asyncio
    async def test_fuzzy_search_disabled(self, cache):
        """Test fuzzy search when disabled."""
        cache.config.enable_fuzzy = False

        results = await cache.fuzzy_search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_cache_key_expiration(self, cache):
        """Test cache key expiration functionality."""
        # Set key with short TTL
        await cache.set("temp_key", "temp_value", ttl=1)

        # Should exist immediately
        exists = await cache.exists("temp_key")
        assert exists is True

    @pytest.mark.asyncio
    async def test_cache_error_handling_graceful(self, cache):
        """Test cache error handling with edge cases."""
        # Test with None value
        success = await cache.set("none_key", None)
        assert success is True

        value = await cache.get("none_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_cache_large_data(self, cache):
        """Test cache with large data objects."""
        large_data = {"data": "x" * 10000, "metadata": {"size": "large"}}

        success = await cache.set("large_data_key", large_data)
        assert success is True

        retrieved = await cache.get("large_data_key")
        assert retrieved == large_data

    @pytest.mark.asyncio
    async def test_cache_unicode_data(self, cache):
        """Test cache with unicode data."""
        unicode_data = {"message": "Hello 世界", "emoji": "😀🎉"}

        success = await cache.set("unicode_key", unicode_data)
        assert success is True

        retrieved = await cache.get("unicode_key")
        assert retrieved == unicode_data

    @pytest.mark.asyncio
    async def test_cache_nested_data_structures(self, cache):
        """Test cache with complex nested data."""
        complex_data = {
            "users": [
                {"id": 1, "profile": {"name": "Alice", "settings": {"theme": "dark"}}},
                {"id": 2, "profile": {"name": "Bob", "settings": {"theme": "light"}}},
            ],
            "metadata": {"version": "1.0", "created": "2023-01-01"},
        }

        success = await cache.set("complex_key", complex_data)
        assert success is True

        retrieved = await cache.get("complex_key")
        assert retrieved == complex_data

    @pytest.mark.asyncio
    async def test_invalidate_pattern_comprehensive(self, cache):
        """Test pattern invalidation with various patterns."""
        # Set up test data
        await cache.set("user:1:profile", {"name": "User 1"})
        await cache.set("user:2:profile", {"name": "User 2"})
        await cache.set("user:1:settings", {"theme": "dark"})
        await cache.set("product:1", {"name": "Product 1"})

        # Invalidate user profiles
        deleted_count = await cache.invalidate_pattern("user:*:profile")
        assert deleted_count == 2

        # Check that only profiles were deleted
        assert await cache.get("user:1:profile") is None
        assert await cache.get("user:2:profile") is None
        assert await cache.get("user:1:settings") is not None
        assert await cache.get("product:1") is not None

    @pytest.mark.asyncio
    async def test_cache_batch_operations(self, cache):
        """Test batch cache operations."""
        # Batch set operations
        batch_data = {f"batch_key_{i}": f"value_{i}" for i in range(50)}

        # Set all keys
        for key, value in batch_data.items():
            await cache.set(key, value)

        # Verify all keys exist
        for key, expected_value in batch_data.items():
            actual_value = await cache.get(key)
            assert actual_value == expected_value

        # Batch delete
        deleted_count = await cache.invalidate_pattern("batch_key_*")
        assert deleted_count == 50

    @pytest.mark.asyncio
    async def test_flush_all(self, cache):
        """Test flushing all cache keys."""
        # Set multiple keys
        await cache.set("test1", "value1")
        await cache.set("test2", "value2")
        await cache.set("test3", "value3")

        # Verify they exist
        assert await cache.get("test1") is not None
        assert await cache.get("test2") is not None
        assert await cache.get("test3") is not None

        # Flush all
        result = await cache.flush_all()
        assert result is True

        # Verify all are gone
        assert await cache.get("test1") is None
        assert await cache.get("test2") is None
        assert await cache.get("test3") is None


class TestCacheConfig:
    """Test cases for CacheConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CacheConfig(enable_env_overrides=False)

        assert config.redis_url == "redis://localhost:6379/0"
        assert config.default_ttl == 300
        assert config.key_prefix == "yokedcache"
        assert config.enable_fuzzy is False
        assert config.max_connections == 50

    def test_config_with_overrides(self):
        """Test configuration with custom values."""
        config = CacheConfig(
            redis_url="redis://custom:6380/1",
            default_ttl=600,
            key_prefix="myapp",
            enable_fuzzy=True,
            fuzzy_threshold=90,
            enable_env_overrides=False,  # Disable env overrides for test
        )

        assert config.redis_url == "redis://custom:6380/1"
        assert config.default_ttl == 600
        assert config.key_prefix == "myapp"
        assert config.enable_fuzzy is True
        assert config.fuzzy_threshold == 90

    def test_redis_url_parsing(self):
        """Test Redis URL parsing."""
        config = CacheConfig(redis_url="redis://user:pass@host:6380/2")

        assert config.redis_host == "host"
        assert config.redis_port == 6380
        assert config.redis_db == 2
        assert config.redis_password == "pass"

    def test_ssl_redis_url(self):
        """Test SSL Redis URL parsing."""
        config = CacheConfig(redis_url="rediss://secure-host:6380/0")

        assert config.redis_ssl is True
        assert config.redis_host == "secure-host"
        assert config.redis_port == 6380


class TestCacheConnection:
    """Test cache connection management."""

    @pytest.mark.asyncio
    async def test_context_manager(self, test_config, fake_redis):
        """Test async context manager functionality."""
        async with YokedCache(config=test_config) as cache:
            # Replace with fake redis for testing
            cache._redis = fake_redis
            cache._connected = True

            await cache.set("context_test", "value")
            result = await cache.get("context_test")
            assert result == "value"

    @pytest.mark.asyncio
    async def test_health_check(self, cache):
        """Test Redis health check."""
        # Should be healthy with fake redis
        healthy = await cache.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test handling of connection errors."""
        # Use invalid Redis URL
        config = CacheConfig(redis_url="redis://invalid-host:9999/0")
        cache = YokedCache(config=config)

        # Should raise connection error
        with pytest.raises(CacheConnectionError):
            await cache.connect()
