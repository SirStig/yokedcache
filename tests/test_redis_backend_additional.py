"""Additional tests for RedisBackend to improve coverage.

We resolve the Redis URL from the environment so tests pass both in the dev
container (redis://redis:56379/0) and in CI where the Redis service is exposed
as localhost:6379. The environment variable YOKEDCACHE_REDIS_URL (exported in
the dev container) takes precedence with a sensible CI fallback.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from yokedcache.backends import RedisBackend
from yokedcache.exceptions import CacheInvalidationError, CacheSerializationError

# (No direct model usage beyond backend operations in these tests)

REDIS_TEST_URL = os.environ.get("YOKEDCACHE_REDIS_URL", "redis://localhost:6379/0")


@pytest.mark.asyncio
async def test_redis_get_miss_increments_miss():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.close = AsyncMock()
        mock_redis.touch = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        result = await backend.get("missing")
        assert result is None
        assert backend._stats.total_misses == 1
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_set_with_tags_pipeline():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
        patch(
            "yokedcache.backends.redis.serialize_data",
            return_value=b"data",
        ),
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        class Pipeline:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            # redis pipeline operations
            setex = AsyncMock()
            sadd = AsyncMock()
            expire = AsyncMock()
            execute = AsyncMock()

        pipeline_mock = Pipeline()
        mock_redis.pipeline = Mock(return_value=pipeline_mock)
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        ok = await backend.set("key", "value", ttl=60, tags={"users"})
        assert ok is True
        pipeline_mock.setex.assert_called()
        pipeline_mock.sadd.assert_called()
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_invalidate_pattern_no_keys():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        deleted = await backend.invalidate_pattern("none:*")
        assert deleted == 0
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_flush_all():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[b"test:a", b"test:b"])
        mock_redis.delete = AsyncMock(return_value=2)
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        ok = await backend.flush_all()
        assert ok is True
        assert backend._stats.total_invalidations >= 2
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_get_stats_memory_and_keys():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.info = AsyncMock(
            side_effect=[{"used_memory": 1234}, {"db0": {"keys": 5}}]
        )
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        stats = await backend.get_stats()
        assert stats.total_memory_bytes == 1234
        assert stats.total_keys == 5
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_fuzzy_search_import_error(monkeypatch):
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[b"test:key1"])  # Not used
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
    await backend.connect()
    # Force ImportError by removing module name
    import sys

    monkeypatch.delitem(sys.modules, "fuzzywuzzy", raising=False)
    results = await backend.fuzzy_search("query")
    assert results == []
    await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_get_all_keys_and_size():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[b"test:x", b"test:y"])
        mock_redis.info = AsyncMock(return_value={"used_memory": 999})
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        keys = await backend.get_all_keys()
        assert len(keys) == 2
        size = await backend.get_size_bytes()
        assert size == 999
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_get_deserialization_fallback():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
        patch("yokedcache.backends.redis.deserialize_data") as mock_deser,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"data")
        mock_redis.touch = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        # First call fails (JSON); second succeeds (PICKLE)
        mock_deser.side_effect = [
            CacheSerializationError(
                data_type="json", operation="deserialize", original_error=None
            ),
            "value",
        ]
        await backend.connect()
        val = await backend.get("k")
        assert val == "value"
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_invalidate_tags_error():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.smembers = AsyncMock(side_effect=Exception("boom"))
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        with pytest.raises(CacheInvalidationError):
            await backend.invalidate_tags({"t"})
        await backend.disconnect()


@pytest.mark.asyncio
async def test_redis_expire_success():
    backend = RedisBackend(redis_url=REDIS_TEST_URL, key_prefix="test")
    mock_pool = AsyncMock()
    mock_pool.disconnect = AsyncMock()
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis") as mock_redis_class,
    ):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.expire = AsyncMock(return_value=1)
        mock_redis.close = AsyncMock()
        mock_redis_class.return_value = mock_redis
        await backend.connect()
        ok = await backend.expire("k", 10)
        assert bool(ok) is True  # redis returns int(1)
        await backend.disconnect()
