"""Additional cache tests for health and flush paths to raise coverage."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from yokedcache import CacheConfig, YokedCache


@pytest.mark.asyncio
async def test_cache_detailed_health_check_paths():
    cfg = CacheConfig(enable_metrics=True, enable_env_overrides=False)
    cache = YokedCache(cfg)
    # Mock internal redis
    mock_r = AsyncMock()
    mock_r.ping.return_value = True
    # For stats
    mock_r.info.side_effect = [
        {"used_memory": 1000},  # memory
        {"db0": {"keys": 5}},  # keyspace
    ]
    mock_r.set.return_value = True
    mock_r.get.return_value = b'"health_check_value"'
    mock_r.delete.return_value = 1
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())

    report = await cache.detailed_health_check()
    assert report["cache"]["redis_available"] is True
    assert "performance" in report


@pytest.mark.asyncio
async def test_delete_prefixed_fallback_raw_first():
    cfg = CacheConfig(key_prefix="pref", enable_env_overrides=False)
    cache = YokedCache(cfg)
    mock_r = AsyncMock()

    # Simulate first raw delete 0 then prefixed delete 1
    async def delete_side_effect(key):  # noqa: D401
        # Return 0 for raw key, 1 for prefixed
        return 0 if key == "raw" else 1

    mock_r.delete.side_effect = delete_side_effect
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    deleted = await cache.delete("raw")
    assert deleted is True


@pytest.mark.asyncio
async def test_flush_all_empty():
    cache = YokedCache(CacheConfig(enable_env_overrides=False))
    mock_r = AsyncMock()
    mock_r.keys.return_value = []
    mock_r.delete.return_value = 0
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    ok = await cache.flush_all()
    assert ok is True


@pytest.mark.asyncio
async def test_expire_failure_returns_false():
    cache = YokedCache(CacheConfig(enable_env_overrides=False))
    mock_r = AsyncMock()
    mock_r.expire.side_effect = RuntimeError("x")
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    res = await cache.expire("k", 10)
    assert res is False
