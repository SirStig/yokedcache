"""
Tests for YokedCache backend implementations.

This module tests Redis, Memory, and Memcached backends.
"""

import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from yokedcache.backends import MemoryBackend, RedisBackend
from yokedcache.backends.base import CacheBackend
from yokedcache.exceptions import CacheConnectionError
from yokedcache.models import CacheStats


class TestCacheBackendInterface:
    """Test the abstract backend interface."""

    def test_abstract_backend_cannot_be_instantiated(self):
        """Test that CacheBackend cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            CacheBackend()  # type: ignore


class TestMemoryBackend:
    """Test the in-memory backend implementation."""

    @pytest.fixture
    async def memory_backend(self):
        """Create a memory backend for testing."""
        backend = MemoryBackend(key_prefix="test", max_size=100)
        await backend.connect()
        yield backend
        await backend.disconnect()

    @pytest.mark.asyncio
    async def test_memory_backend_connection(self):
        """Test memory backend connection and disconnection."""
        backend = MemoryBackend()

        # Test initial state
        assert not backend.is_connected

        # Test connection
        await backend.connect()
        assert backend.is_connected
        assert await backend.health_check()

        # Test disconnection
        await backend.disconnect()
        assert not backend.is_connected

    @pytest.mark.asyncio
    async def test_memory_backend_basic_operations(self, memory_backend):
        """Test basic get/set/delete operations."""
        # Test set and get
        assert await memory_backend.set("test_key", "test_value", ttl=300)
        value = await memory_backend.get("test_key")
        assert value == "test_value"

        # Test key existence
        assert await memory_backend.exists("test_key")
        assert not await memory_backend.exists("nonexistent_key")

        # Test delete
        assert await memory_backend.delete("test_key")
        assert not await memory_backend.exists("test_key")
        assert await memory_backend.get("test_key") is None

    @pytest.mark.asyncio
    async def test_memory_backend_ttl_expiration(self, memory_backend):
        """Test TTL expiration in memory backend."""
        # Set with short TTL
        await memory_backend.set("short_ttl_key", "value", ttl=1)

        # Should exist immediately
        assert await memory_backend.exists("short_ttl_key")

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        assert not await memory_backend.exists("short_ttl_key")
        assert await memory_backend.get("short_ttl_key") is None

    @pytest.mark.asyncio
    async def test_memory_backend_tags(self, memory_backend):
        """Test tag-based operations."""
        # Set values with tags
        await memory_backend.set("user:1", {"name": "Alice"}, tags={"users", "active"})
        await memory_backend.set("user:2", {"name": "Bob"}, tags={"users"})
        await memory_backend.set("post:1", {"title": "Test"}, tags={"posts"})

        # Test tag invalidation
        invalidated = await memory_backend.invalidate_tags({"users"})
        assert invalidated == 2

        # Check that user keys are gone
        assert not await memory_backend.exists("user:1")
        assert not await memory_backend.exists("user:2")

        # But post key should remain
        assert await memory_backend.exists("post:1")

    @pytest.mark.asyncio
    async def test_memory_backend_pattern_invalidation(self, memory_backend):
        """Test pattern-based invalidation."""
        # Set multiple keys
        await memory_backend.set("user:1", "Alice")
        await memory_backend.set("user:2", "Bob")
        await memory_backend.set("post:1", "Test Post")

        # Invalidate user keys with pattern
        invalidated = await memory_backend.invalidate_pattern("user:*")
        assert invalidated == 2

        # Check results
        assert not await memory_backend.exists("user:1")
        assert not await memory_backend.exists("user:2")
        assert await memory_backend.exists("post:1")

    @pytest.mark.asyncio
    async def test_memory_backend_max_size_eviction(self):
        """Test LRU eviction when max_size is reached."""
        backend = MemoryBackend(max_size=3)
        await backend.connect()

        try:
            # Fill up the cache
            await backend.set("key1", "value1")
            await backend.set("key2", "value2")
            await backend.set("key3", "value3")

            # All should exist
            assert await backend.exists("key1")
            assert await backend.exists("key2")
            assert await backend.exists("key3")

            # Add one more - should evict least recently used
            await backend.set("key4", "value4")

            # One of the older keys should be evicted
            keys_count = sum(
                [
                    await backend.exists("key1"),
                    await backend.exists("key2"),
                    await backend.exists("key3"),
                    await backend.exists("key4"),
                ]
            )
            assert keys_count == 3  # Only 3 keys should remain

        finally:
            await backend.disconnect()

    @pytest.mark.asyncio
    async def test_memory_backend_expire(self, memory_backend):
        """Test setting expiration on existing keys."""
        await memory_backend.set("test_key", "value", ttl=3600)

        # Should exist
        assert await memory_backend.exists("test_key")

        # Set short expiration
        assert await memory_backend.expire("test_key", 1)

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        assert not await memory_backend.exists("test_key")

    @pytest.mark.asyncio
    async def test_memory_backend_flush_all(self, memory_backend):
        """Test flushing all keys."""
        # Set multiple keys
        await memory_backend.set("key1", "value1")
        await memory_backend.set("key2", "value2")
        await memory_backend.set("key3", "value3")

        # Flush all
        assert await memory_backend.flush_all()

        # All should be gone
        assert not await memory_backend.exists("key1")
        assert not await memory_backend.exists("key2")
        assert not await memory_backend.exists("key3")

    @pytest.mark.asyncio
    async def test_memory_backend_stats(self, memory_backend):
        """Test statistics collection."""
        # Perform some operations
        await memory_backend.set("key1", "value1")
        await memory_backend.set("key2", "value2")

        await memory_backend.get("key1")  # hit
        await memory_backend.get("nonexistent")  # miss

        await memory_backend.delete("key1")

        # Get stats
        stats = await memory_backend.get_stats()

        assert isinstance(stats, CacheStats)
        assert stats.total_hits == 1
        assert stats.total_misses == 1
        assert stats.total_sets == 2
        assert stats.total_deletes == 1
        assert stats.total_keys == 1  # Only key2 remains
        assert stats.total_memory_bytes > 0
        assert stats.uptime_seconds > 0

    @pytest.mark.asyncio
    async def test_memory_backend_fuzzy_search(self, memory_backend):
        """Test fuzzy search functionality."""
        # Set some test data
        await memory_backend.set("user:alice", {"name": "Alice Smith"})
        await memory_backend.set("user:bob", {"name": "Bob Jones"})
        await memory_backend.set("user:charlie", {"name": "Charlie Brown"})

        # Test fuzzy search
        results = await memory_backend.fuzzy_search(
            "alice", threshold=70, max_results=5
        )

        # Should find the alice user
        assert len(results) >= 1
        found_alice = any("alice" in result.key for result in results)
        assert found_alice

    @pytest.mark.asyncio
    async def test_memory_backend_get_all_keys(self, memory_backend):
        """Test getting all keys with pattern."""
        # Set test data
        await memory_backend.set("user:1", "Alice")
        await memory_backend.set("user:2", "Bob")
        await memory_backend.set("post:1", "Test Post")

        # Get all user keys
        user_keys = await memory_backend.get_all_keys("user:*")
        assert len(user_keys) == 2

        # Get all keys
        all_keys = await memory_backend.get_all_keys("*")
        assert len(all_keys) == 3


REDIS_TEST_URL = os.environ.get("YOKEDCACHE_REDIS_URL", "redis://localhost:6379/0")


class TestRedisBackend:
    """Test the Redis backend implementation."""

    @pytest.fixture
    async def redis_backend(self):
        """Create a Redis backend for testing with fake Redis."""
        backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")

        # Mock Redis connection
        # Create proper async mocks
        mock_pool = AsyncMock()
        mock_pool.disconnect = AsyncMock()

        with (
            patch(
                "redis.asyncio.ConnectionPool.from_url",
                return_value=mock_pool,
            ),
            patch("redis.asyncio.Redis") as mock_redis_class,
        ):

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis.get = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis.delete = AsyncMock()
            mock_redis.exists = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_redis.keys = AsyncMock()
            mock_redis.smembers = AsyncMock()
            mock_redis.close = AsyncMock()
            mock_redis.info = AsyncMock()
            mock_redis.touch = AsyncMock()

            # Setup pipeline mock
            pipeline_mock = AsyncMock()
            pipeline_mock.setex = AsyncMock()
            pipeline_mock.sadd = AsyncMock()
            pipeline_mock.expire = AsyncMock()
            pipeline_mock.execute = AsyncMock()
            mock_redis.pipeline = Mock(return_value=pipeline_mock)

            mock_redis_class.return_value = mock_redis
            backend._redis = mock_redis
            backend._pool = mock_pool

            await backend.connect()
            yield backend, mock_redis
            await backend.disconnect()

    @pytest.mark.asyncio
    async def test_redis_backend_connection(self):
        """Test Redis backend connection."""
        backend = RedisBackend()

        mock_pool = AsyncMock()
        mock_pool.disconnect = AsyncMock()

        with (
            patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
            patch("redis.asyncio.Redis") as mock_redis_class,
        ):

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis.close = AsyncMock()
            mock_redis_class.return_value = mock_redis

            # Test successful connection
            await backend.connect()
            assert backend.is_connected
            mock_redis.ping.assert_called_once()

            await backend.disconnect()

    @pytest.mark.asyncio
    async def test_redis_backend_connection_failure(self):
        """Test Redis backend connection failure."""
        backend = RedisBackend()

        with (
            patch("redis.asyncio.ConnectionPool.from_url"),
            patch("redis.asyncio.Redis") as mock_redis_class,
        ):

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))
            mock_redis_class.return_value = mock_redis

            # Test connection failure
            with pytest.raises(CacheConnectionError):
                await backend.connect()

    @pytest.mark.asyncio
    async def test_redis_backend_basic_operations(self, redis_backend):
        """Test basic Redis operations."""
        backend, mock_redis = redis_backend

        # Mock responses
        mock_redis.get.return_value = b'"test_value"'
        mock_redis.setex.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.exists.return_value = 1

        # Test set
        result = await backend.set("test_key", "test_value", ttl=300)
        assert result

        # Test get
        value = await backend.get("test_key")
        assert value == "test_value"

        # Test exists
        exists = await backend.exists("test_key")
        assert exists

        # Test delete
        deleted = await backend.delete("test_key")
        assert deleted

    @pytest.mark.asyncio
    async def test_redis_backend_health_check(self, redis_backend):
        """Test Redis health check."""
        backend, mock_redis = redis_backend

        # Test healthy
        mock_redis.ping = AsyncMock()
        assert await backend.health_check()

        # Test unhealthy
        mock_redis.ping = AsyncMock(side_effect=Exception("Redis down"))
        assert not await backend.health_check()

    @pytest.mark.asyncio
    async def test_redis_backend_pattern_invalidation(self, redis_backend):
        """Test pattern-based invalidation."""
        backend, mock_redis = redis_backend

        # Mock finding keys and deleting them
        mock_redis.keys.return_value = [b"test:user:1", b"test:user:2"]
        mock_redis.delete.return_value = 2

        invalidated = await backend.invalidate_pattern("user:*")
        assert invalidated == 2

        mock_redis.keys.assert_called_once()
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_backend_tag_invalidation(self, redis_backend):
        """Test tag-based invalidation."""
        backend, mock_redis = redis_backend

        # Mock tag keys and deletion
        mock_redis.smembers.return_value = {b"test:user:1", b"test:user:2"}
        mock_redis.delete.return_value = 2

        invalidated = await backend.invalidate_tags({"users"})
        assert invalidated == 2


@pytest.mark.skipif(
    "MemcachedBackend" not in dir()
    or pytest.importorskip(
        "yokedcache.backends", reason="Memcached backend not available"
    ).MEMCACHED_AVAILABLE
    is False,
    reason="Memcached dependencies not available",
)
class TestMemcachedBackend:
    """Test the Memcached backend implementation."""

    @pytest.fixture
    async def memcached_backend(self):
        """Create a Memcached backend for testing."""
        with patch("aiomcache.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.version = AsyncMock()
            mock_client.get = AsyncMock()
            mock_client.set = AsyncMock()
            mock_client.delete = AsyncMock()
            mock_client.stats = AsyncMock()
            mock_client.flush_all = AsyncMock()
            mock_client.close = AsyncMock()

            mock_client_class.return_value = mock_client

            from yokedcache.backends import MemcachedBackend

            backend = MemcachedBackend(servers=["localhost:11211"])
            backend._client = mock_client

            await backend.connect()
            yield backend, mock_client
            await backend.disconnect()

    @pytest.mark.asyncio
    async def test_memcached_backend_basic_operations(self, memcached_backend):
        """Test basic Memcached operations."""
        backend, mock_client = memcached_backend

        # Mock responses
        mock_client.get.return_value = b"test_value"
        mock_client.set.return_value = True
        mock_client.delete.return_value = True

        # Test set
        with patch("yokedcache.utils.serialize_data", return_value=b"test_value"):
            result = await backend.set("test_key", "test_value", ttl=300)
            assert result

        # Test get
        with patch("yokedcache.utils.deserialize_data", return_value="test_value"):
            value = await backend.get("test_key")
            assert value == "test_value"

        # Test delete
        deleted = await backend.delete("test_key")
        assert deleted
