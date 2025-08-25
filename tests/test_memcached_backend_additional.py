"""Additional tests for MemcachedBackend to improve coverage.

These tests mock aiomcache to avoid real Memcached dependency.
"""

from unittest.mock import AsyncMock, patch

import pytest

# Skip entire module if aiomcache not installed
pytestmark = pytest.mark.skipif(
    __import__("importlib").util.find_spec("aiomcache") is None,
    reason="aiomcache not installed",
)


@pytest.mark.asyncio
async def test_memcached_connect_and_health():
    with patch("aiomcache.Client") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.version = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        from yokedcache.backends import MemcachedBackend

        backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="test")
        await backend.connect()
        assert backend.is_connected
        healthy = await backend.health_check()
        assert healthy is True
        await backend.disconnect()
        assert not backend.is_connected


@pytest.mark.asyncio
async def test_memcached_get_miss_and_hit():
    with (
        patch("aiomcache.Client") as mock_client_cls,
        patch("yokedcache.backends.memcached.deserialize_data", return_value="val"),
    ):
        mock_client = AsyncMock()
        mock_client.version = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[None, b"serialized"])
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        from yokedcache.backends import MemcachedBackend

        backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="t")
        await backend.connect()
        v1 = await backend.get("k")
        assert v1 is None
        v2 = await backend.get("k")
        assert v2 == "val"
        assert backend._stats.total_misses == 1
        assert backend._stats.total_hits == 1
        await backend.disconnect()


@pytest.mark.asyncio
async def test_memcached_set_with_tags_and_invalidate():
    with (
        patch("aiomcache.Client") as mock_client_cls,
        patch("yokedcache.backends.memcached.serialize_data", return_value=b"s"),
    ):
        mock_client = AsyncMock()
        mock_client.version = AsyncMock()
        mock_client.set = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        from yokedcache.backends import MemcachedBackend

        backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="t")
        await backend.connect()
        ok = await backend.set("k", "v", tags={"users"})
        assert ok
        assert "users" in backend._tag_storage
        invalidated = await backend.invalidate_tags({"users"})
        assert invalidated == 1
        await backend.disconnect()


@pytest.mark.asyncio
async def test_memcached_flush_all_and_stats():
    with patch("aiomcache.Client") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.version = AsyncMock()
        mock_client.flush_all = AsyncMock()
        mock_client.stats = AsyncMock(
            return_value={b"bytes": b"10", b"curr_items": b"2"}
        )
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        from yokedcache.backends import MemcachedBackend

        backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="t")
        await backend.connect()
        await backend.flush_all()
        stats = await backend.get_stats()
        assert stats.total_memory_bytes == 10
        assert stats.total_keys == 2
        await backend.disconnect()


@pytest.mark.asyncio
async def test_memcached_fuzzy_search_and_get_all_keys():
    with patch("aiomcache.Client") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.version = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        from yokedcache.backends import MemcachedBackend

        backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="t")
        await backend.connect()
        # Without fuzzywuzzy likely returns [] but ensure method call doesn't error
        results = await backend.fuzzy_search("query")
        assert isinstance(results, list)
        keys = await backend.get_all_keys()
        assert keys == []
        await backend.disconnect()
