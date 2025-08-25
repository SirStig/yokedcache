"""Extra cache coverage tests for untested branches in cache.py."""

import pickle
import socket
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache import CacheConfig, YokedCache
from yokedcache.exceptions import CacheInvalidationError


@pytest.mark.asyncio
async def test_build_key_already_prefixed():
    cfg = CacheConfig(key_prefix="pref", enable_env_overrides=False)
    cache = YokedCache(cfg)
    assert cache._build_key("pref:abc") == "pref:abc"


@pytest.mark.asyncio
async def test_get_pickle_fallback():
    cache = YokedCache(CacheConfig(enable_env_overrides=False))
    pickled = pickle.dumps({"a": 1})
    mock_r = AsyncMock()
    mock_r.get.return_value = pickled
    mock_r.touch.return_value = True
    cache._connected = True
    cache._redis = mock_r

    # Simple context manager returning mock redis
    class CM:
        async def __aenter__(self):  # noqa: D401
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    val = await cache.get("k")
    assert val == {"a": 1}


@pytest.mark.asyncio
async def test_exists_prefixed():
    cache = YokedCache(CacheConfig(key_prefix="t", enable_env_overrides=False))
    mock_r = AsyncMock()
    mock_r.exists.return_value = 1
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    assert await cache.exists("t:abc") is True


@pytest.mark.asyncio
async def test_invalidate_pattern_error():
    cache = YokedCache(CacheConfig(enable_env_overrides=False))
    mock_r = AsyncMock()
    mock_r.keys.side_effect = RuntimeError("boom")
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    with pytest.raises(CacheInvalidationError):
        await cache.invalidate_pattern("*")


@pytest.mark.asyncio
async def test_invalidate_tags_error():
    cache = YokedCache(CacheConfig(enable_env_overrides=False))
    mock_r = AsyncMock()
    mock_r.smembers.side_effect = RuntimeError("x")
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    with pytest.raises(CacheInvalidationError):
        await cache.invalidate_tags(["t1"])  # noqa: PT012


@pytest.mark.asyncio
async def test_get_comprehensive_metrics_disabled():
    cfg = CacheConfig(enable_metrics=False, enable_env_overrides=False)
    cache = YokedCache(cfg)
    with patch.object(cache, "get_stats") as gs:
        gs.return_value = cache._stats
        data = await cache.get_comprehensive_metrics()
    assert data["metrics_enabled"] is False


@pytest.mark.asyncio
async def test_fuzzy_search_by_tags(monkeypatch):
    cfg = CacheConfig(enable_fuzzy=True, enable_env_overrides=False)
    cache = YokedCache(cfg)
    mock_r = AsyncMock()
    mock_r.smembers.return_value = {b"pref:a", b"pref:b"}
    mock_r.keys.return_value = []
    mock_r.get.return_value = b"{}"
    cache._connected = True
    cache._redis = mock_r

    class CM:
        async def __aenter__(self):
            return mock_r

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cast(Any, cache)._get_redis = MagicMock(return_value=CM())
    # Provide fake fuzzy library results

    class DummyProcess:
        @staticmethod
        def extract(query, strings, scorer, limit):  # noqa: D401
            return [(strings[0], 95)] if strings else []

    monkeypatch.setitem(
        __import__("sys").modules,
        "fuzzywuzzy.process",
        DummyProcess,
    )

    class DummyFuzz:  # scorer placeholder
        partial_ratio = object()

    monkeypatch.setitem(
        __import__("sys").modules,
        "fuzzywuzzy.fuzz",
        DummyFuzz,
    )
    results = await cache.fuzzy_search("a", tags={"tag1"})
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_in_memory_fallback_connection_hard_failure(monkeypatch):
    cfg = CacheConfig(
        redis_url="redis://no-such-host.invalid/0",
        enable_memory_fallback=True,
        fallback_enabled=True,
        enable_env_overrides=False,
    )
    cache = YokedCache(cfg)
    # Force DNS failure
    with patch("redis.asyncio.from_url", side_effect=socket.gaierror("dns")):
        await cache.connect()
    assert getattr(cache, "_fallback_mode", False) is True
    # In degraded mode set() should return False regardless
    res = await cache.set("k", "v")
    assert res is False


@pytest.mark.asyncio
async def test_start_stop_metrics_collection():
    cfg = CacheConfig(enable_metrics=True, enable_env_overrides=False)
    cache = YokedCache(cfg)
    # Start (spawns task) then stop; no assertions other than no exception
    cache.start_metrics_collection()
    await cache.stop_metrics_collection()
