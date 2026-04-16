"""
Tests for uncovered paths in backends/memcached.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache.backends.memcached import MemcachedBackend


def _make_backend_with_mock_client():
    """Create a MemcachedBackend with a mock client."""
    backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="test")
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.version = AsyncMock(return_value=b"1.6.0")
    mock_client.stats = AsyncMock(
        return_value={b"curr_items": b"10", b"bytes": b"1024"}
    )
    mock_client.flush_all = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    backend._client = mock_client
    backend._connected = True
    return backend


# ---------------------------------------------------------------------------
# MemcachedBackend initialization
# ---------------------------------------------------------------------------


def test_memcached_init():
    backend = MemcachedBackend(servers=["localhost:11211"], key_prefix="test")
    assert backend.key_prefix == "test"
    assert len(backend.server_tuples) == 1


def test_memcached_init_no_port():
    backend = MemcachedBackend(servers=["localhost"], key_prefix="test")
    assert backend.server_tuples[0] == ("localhost", 11211)


def test_memcached_init_without_aiomcache():
    with patch.dict("sys.modules", {"aiomcache": None}):
        import importlib

        from yokedcache.backends import memcached as mc_mod

        with patch.object(mc_mod, "AIOMCACHE_AVAILABLE", False):
            with pytest.raises(ImportError):
                MemcachedBackend(servers=["localhost:11211"])


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_connected():
    backend = _make_backend_with_mock_client()
    result = await backend.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_health_check_not_connected():
    backend = MemcachedBackend(servers=["localhost:11211"])
    result = await backend.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_health_check_exception():
    backend = _make_backend_with_mock_client()
    backend._client.version = AsyncMock(side_effect=Exception("connection failed"))
    result = await backend.health_check()
    assert result is False


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_miss():
    backend = _make_backend_with_mock_client()
    result = await backend.get("missing_key")
    assert result is None


@pytest.mark.asyncio
async def test_get_hit():
    from yokedcache.models import SerializationMethod
    from yokedcache.utils import serialize_for_cache

    backend = _make_backend_with_mock_client()
    serialized = serialize_for_cache({"data": "value"}, SerializationMethod.JSON)
    backend._client.get = AsyncMock(return_value=serialized)

    result = await backend.get("hit_key")
    assert result == {"data": "value"}


@pytest.mark.asyncio
async def test_get_deserialization_error():
    backend = _make_backend_with_mock_client()
    backend._client.get = AsyncMock(return_value=b"\xff\xfe\x00bad_data")

    result = await backend.get("bad_key")
    assert result is None


@pytest.mark.asyncio
async def test_get_exception():
    backend = _make_backend_with_mock_client()
    backend._client.get = AsyncMock(side_effect=Exception("get failed"))

    result = await backend.get("any_key")
    assert result is None


@pytest.mark.asyncio
async def test_get_no_client():
    backend = MemcachedBackend(servers=["localhost:11211"])
    result = await backend.get("key")
    assert result is None


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_success():
    backend = _make_backend_with_mock_client()
    result = await backend.set("set_key", {"data": "value"})
    assert result is True


@pytest.mark.asyncio
async def test_set_with_tags():
    backend = _make_backend_with_mock_client()
    result = await backend.set("tagged_key", "value", tags={"tag1", "tag2"})
    assert result is True
    # Check tags were stored
    assert "tag1" in backend._tag_storage or "tag2" in backend._tag_storage


@pytest.mark.asyncio
async def test_set_exception():
    backend = _make_backend_with_mock_client()
    backend._client.set = AsyncMock(side_effect=Exception("set failed"))

    result = await backend.set("fail_key", "value")
    assert result is False


@pytest.mark.asyncio
async def test_set_no_client():
    backend = MemcachedBackend(servers=["localhost:11211"])
    result = await backend.set("key", "value")
    assert result is False


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_success():
    backend = _make_backend_with_mock_client()
    # Set a key first to have tags
    await backend.set("tagged", "val", tags={"t1"})
    result = await backend.delete("tagged")
    assert result is True


@pytest.mark.asyncio
async def test_delete_no_client():
    backend = MemcachedBackend(servers=["localhost:11211"])
    result = await backend.delete("key")
    assert result is False


@pytest.mark.asyncio
async def test_delete_exception():
    backend = _make_backend_with_mock_client()
    backend._client.delete = AsyncMock(side_effect=Exception("delete failed"))
    result = await backend.delete("any_key")
    assert result is False


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exists_hit():
    from yokedcache.models import SerializationMethod
    from yokedcache.utils import serialize_for_cache

    backend = _make_backend_with_mock_client()
    serialized = serialize_for_cache("value", SerializationMethod.JSON)
    backend._client.get = AsyncMock(return_value=serialized)

    result = await backend.exists("existing_key")
    assert result is True


@pytest.mark.asyncio
async def test_exists_miss():
    backend = _make_backend_with_mock_client()
    backend._client.get = AsyncMock(return_value=None)
    result = await backend.exists("missing_key")
    assert result is False


# ---------------------------------------------------------------------------
# invalidate_pattern
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_pattern():
    backend = _make_backend_with_mock_client()
    # Add some keys to simulate
    await backend.set("user:1", "alice")
    await backend.set("user:2", "bob")
    # Memcached doesn't support pattern deletion natively, should return 0
    result = await backend.invalidate_pattern("user:*")
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# invalidate_tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_tags():
    backend = _make_backend_with_mock_client()
    await backend.set("tagged_k", "val", tags={"my_tag"})
    result = await backend.invalidate_tags({"my_tag"})
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# flush_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_all():
    backend = _make_backend_with_mock_client()
    result = await backend.flush_all()
    assert result is True


@pytest.mark.asyncio
async def test_flush_all_no_client():
    backend = MemcachedBackend(servers=["localhost:11211"])
    result = await backend.flush_all()
    assert result is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stats():
    backend = _make_backend_with_mock_client()
    stats = await backend.get_stats()
    assert stats is not None
    assert stats.uptime_seconds >= 0


# ---------------------------------------------------------------------------
# disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect():
    backend = _make_backend_with_mock_client()
    await backend.disconnect()
    assert backend._connected is False
    backend._client.close.assert_called()
