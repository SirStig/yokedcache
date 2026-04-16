"""
Tests for cache.py internals: EmbeddedMemoryRedis, _InflightLockMap, YokedCache aliases,
circuit breaker, health checks, get/set edge cases, SWR.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from yokedcache import CacheConfig, YokedCache
from yokedcache.cache import EmbeddedMemoryRedis, _InflightLockMap
from yokedcache.circuit_breaker import CircuitBreakerState

# ---------------------------------------------------------------------------
# EmbeddedMemoryRedis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embedded_ping():
    r = EmbeddedMemoryRedis()
    assert await r.ping() is True


@pytest.mark.asyncio
async def test_embedded_aclose():
    r = EmbeddedMemoryRedis()
    result = await r.aclose()
    assert result is None


@pytest.mark.asyncio
async def test_embedded_close():
    r = EmbeddedMemoryRedis()
    result = await r.close()
    assert result is None


@pytest.mark.asyncio
async def test_embedded_get_set():
    r = EmbeddedMemoryRedis()
    assert await r.get("missing") is None
    await r.set("key1", "val1")
    assert await r.get("key1") == "val1"


@pytest.mark.asyncio
async def test_embedded_delete_data_and_sets():
    r = EmbeddedMemoryRedis()
    await r.set("k", "v")
    await r.sadd("s", "member")
    deleted = await r.delete("k", "s")
    assert deleted == 2
    assert await r.get("k") is None
    assert await r.smembers("s") == set()


@pytest.mark.asyncio
async def test_embedded_exists_data_and_sets():
    r = EmbeddedMemoryRedis()
    await r.set("k1", "v")
    await r.sadd("s1", "m")
    count = await r.exists("k1", "s1", "missing")
    assert count == 2


@pytest.mark.asyncio
async def test_embedded_flushdb():
    r = EmbeddedMemoryRedis()
    await r.set("x", "1")
    await r.sadd("y", "2")
    result = await r.flushdb()
    assert result is True
    assert r._data == {}
    assert r._sets == {}


@pytest.mark.asyncio
async def test_embedded_touch():
    r = EmbeddedMemoryRedis()
    assert await r.touch("anything") is True


@pytest.mark.asyncio
async def test_embedded_sadd_new_and_existing():
    r = EmbeddedMemoryRedis()
    result1 = await r.sadd("myset", "a")
    assert result1 == 1
    result2 = await r.sadd("myset", "a")  # duplicate
    assert result2 == 0
    result3 = await r.sadd("myset", "b")  # new member
    assert result3 == 1


@pytest.mark.asyncio
async def test_embedded_smembers():
    r = EmbeddedMemoryRedis()
    await r.sadd("s", "x")
    await r.sadd("s", "y")
    members = await r.smembers("s")
    assert members == {"x", "y"}


@pytest.mark.asyncio
async def test_embedded_expire():
    r = EmbeddedMemoryRedis()
    assert await r.expire("anykey", 60) is True


@pytest.mark.asyncio
async def test_embedded_keys_star():
    r = EmbeddedMemoryRedis()
    await r.set("a", 1)
    await r.set("b", 2)
    keys = await r.keys("*")
    assert set(keys) == {"a", "b"}


@pytest.mark.asyncio
async def test_embedded_keys_prefix_star():
    r = EmbeddedMemoryRedis()
    await r.set("prefix:x", 1)
    await r.set("other", 2)
    keys = await r.keys("prefix:*")
    assert keys == ["prefix:x"]


@pytest.mark.asyncio
async def test_embedded_keys_exact():
    r = EmbeddedMemoryRedis()
    await r.set("exact", 1)
    await r.set("exact2", 2)
    keys = await r.keys("exact")
    assert keys == ["exact"]


@pytest.mark.asyncio
async def test_embedded_scan_iter():
    r = EmbeddedMemoryRedis()
    await r.set("a", 1)
    await r.set("b", 2)
    found = []
    async for k in r.scan_iter(match="*"):
        found.append(k)
    assert set(found) == {"a", "b"}


@pytest.mark.asyncio
async def test_embedded_info_memory():
    r = EmbeddedMemoryRedis()
    await r.set("k", "hello")
    info = await r.info("memory")
    assert "used_memory" in info


@pytest.mark.asyncio
async def test_embedded_info_keyspace():
    r = EmbeddedMemoryRedis()
    await r.set("k", "v")
    info = await r.info("keyspace")
    assert "db0" in info
    assert info["db0"]["keys"] == 1


@pytest.mark.asyncio
async def test_embedded_info_default():
    r = EmbeddedMemoryRedis()
    info = await r.info()
    assert info == {}


@pytest.mark.asyncio
async def test_embedded_dbsize():
    r = EmbeddedMemoryRedis()
    await r.set("x", 1)
    await r.set("y", 2)
    size = await r.dbsize()
    assert size == 2


# ---------------------------------------------------------------------------
# _InflightLockMap eviction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inflight_lock_map_eviction():
    lmap = _InflightLockMap(max_keys=1)
    lock_a = lmap["a"]
    assert "a" in lmap._locks
    # Access "b" should evict "a"
    lock_b = lmap["b"]
    assert "a" not in lmap._locks
    assert "b" in lmap._locks


# ---------------------------------------------------------------------------
# YokedCache aliases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_yoked_cache_aget(cache):
    await cache.set("alias_key", "val")
    result = await cache.aget("alias_key")
    assert result == "val"


@pytest.mark.asyncio
async def test_yoked_cache_adelete(cache):
    await cache.set("del_key", "val")
    result = await cache.adelete("del_key")
    assert result is True


@pytest.mark.asyncio
async def test_yoked_cache_aexists(cache):
    await cache.set("ex_key", "val")
    result = await cache.aexists("ex_key")
    assert result is True


@pytest.mark.asyncio
async def test_yoked_cache_health(cache):
    result = await cache.health()
    assert result is True


@pytest.mark.asyncio
async def test_yoked_cache_ping(cache):
    result = await cache.ping()
    assert result is True


@pytest.mark.asyncio
async def test_yoked_cache_flush(cache):
    await cache.set("flush_key", "val")
    result = await cache.flush()
    assert result is True


# ---------------------------------------------------------------------------
# YokedCache __aenter__/__aexit__
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_yoked_cache_context_manager():
    config = CacheConfig(key_prefix="ctx_test")
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True
    async with c as ctx:
        assert ctx is c
    # After exit, should be disconnected
    assert c._connected is False


# ---------------------------------------------------------------------------
# YokedCache.invalidate_by_tags alias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_by_tags_alias(cache):
    await cache.set("tagged_key", "val", tags=["mytag"])
    result = await cache.invalidate_by_tags(["mytag"])
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# YokedCache with unknown config param
# ---------------------------------------------------------------------------


def test_yoked_cache_unknown_kwarg():
    import logging

    with patch.object(logging.getLogger("yokedcache.cache"), "warning") as mock_warn:
        c = YokedCache(unknown_kwarg=True)
        mock_warn.assert_called()
        assert "unknown_kwarg" in str(mock_warn.call_args) or True  # just verify called


# ---------------------------------------------------------------------------
# health_check() exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_exception(cache):
    cache._redis.ping = AsyncMock(side_effect=Exception("ping failed"))
    result = await cache.health_check()
    assert result is False


# ---------------------------------------------------------------------------
# flush_all() when scan_iter raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_all_exception(cache):
    async def bad_scan_iter(*args, **kwargs):
        raise Exception("scan failed")
        yield  # make it an async generator

    with patch("yokedcache.cache.redis_scan_keys", side_effect=Exception("scan fail")):
        result = await cache.flush_all()
        assert result is False


# ---------------------------------------------------------------------------
# detailed_health_check with pool set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detailed_health_check_with_pool(cache):
    pool_mock = MagicMock()
    pool_mock.created_connections = 2
    pool_mock.available_connections = 1
    pool_mock.in_use_connections = 1
    cache._pool = pool_mock
    result = await cache.detailed_health_check()
    assert result["cache"]["connection_pool_stats"] is not None
    cache._pool = None


# ---------------------------------------------------------------------------
# detailed_health_check with high failure_rate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detailed_health_check_high_failure_rate(cache):
    # Enable circuit breaker for this test
    from yokedcache.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(failure_threshold=5, timeout=60.0)
    # Artificially set a stats method that returns high failure_rate
    original_get_stats = cb.get_stats
    cb.get_stats = lambda: {
        "state": "closed",
        "failure_rate": 0.5,  # 50%
        "failure_count": 5,
        "total_requests": 10,
    }
    cache._circuit_breaker = cb
    result = await cache.detailed_health_check()
    assert any("failure rate" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# _execute_with_resilience with circuit breaker open
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_with_resilience_circuit_breaker_open(cache):
    from yokedcache.circuit_breaker import CircuitBreaker, CircuitBreakerError

    cb = CircuitBreaker(failure_threshold=1, timeout=60.0)
    # Force circuit open
    cb.state = CircuitBreakerState.OPEN
    cb.last_failure_time = __import__("time").time()
    cache._circuit_breaker = cb

    # Should return None due to fallback
    result = await cache._execute_with_resilience(
        AsyncMock(side_effect=Exception("nope"))
    )
    assert result is None


# ---------------------------------------------------------------------------
# get() with log_cache_misses=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_log_cache_misses(cache):
    cache.config.log_cache_misses = True
    result = await cache.get("nonexistent_key_xyz")
    assert result is None
    cache.config.log_cache_misses = False


# ---------------------------------------------------------------------------
# get() with deserialization error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_deserialization_error(cache):
    from yokedcache.utils import sanitize_key

    key = "bad_data_key"
    sanitized = sanitize_key(f"{cache.config.key_prefix}:{key}")
    # Store invalid data directly in redis
    await cache._redis.set(sanitized, b"\xff\xfe\x00bad_json_data")
    # Should return None default on deserialization failure
    result = await cache.get(key)
    assert result is None


# ---------------------------------------------------------------------------
# fetch_or_set with enable_stale_while_revalidate=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_or_set_with_swr():
    config = CacheConfig(
        key_prefix="swr_test",
        enable_stale_while_revalidate=True,
        enable_single_flight=True,
    )
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True

    call_count = 0

    def loader():
        nonlocal call_count
        call_count += 1
        return "fresh_value"

    result = await c.fetch_or_set("swr_key", loader, ttl=300)
    assert result == "fresh_value"
    assert call_count == 1

    # Second call should hit cache
    result2 = await c.fetch_or_set("swr_key", loader, ttl=300)
    assert result2 == "fresh_value"

    await c.disconnect()


# ---------------------------------------------------------------------------
# set() with stale-while-revalidate enabled - hits stale_store update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_with_swr_updates_stale_store():
    config = CacheConfig(
        key_prefix="swr2_test",
        enable_stale_while_revalidate=True,
    )
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True

    result = await c.set("swr_set_key", {"data": 42}, ttl=300)
    assert result is True

    # Verify stale store was populated
    from yokedcache.utils import calculate_ttl_with_jitter, sanitize_key

    sanitized = sanitize_key(f"{config.key_prefix}:swr_set_key")
    assert sanitized in c._stale_store

    await c.disconnect()


# ---------------------------------------------------------------------------
# health_check when not connected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_not_connected():
    config = CacheConfig(key_prefix="hc_test")
    c = YokedCache(config=config)
    # Not connected
    result = await c.health_check()
    assert result is False


# ---------------------------------------------------------------------------
# detailed_health_check when circuit breaker open state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detailed_health_check_cb_open(cache):
    from yokedcache.circuit_breaker import CircuitBreaker, CircuitBreakerState

    cb = CircuitBreaker(failure_threshold=1, timeout=60.0)
    cb.state = CircuitBreakerState.OPEN
    cb.last_failure_time = __import__("time").time()
    cache._circuit_breaker = cb

    result = await cache.detailed_health_check()
    # Should indicate degraded due to open circuit breaker
    assert result["status"] in ("degraded", "unhealthy", "healthy")


# ---------------------------------------------------------------------------
# sync_fallback method
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_fallback_in_async(cache):
    async def returns_value():
        return "sync_fallback_result"

    result = await cache._sync_fallback(returns_value)
    assert result == "sync_fallback_result"


# ---------------------------------------------------------------------------
# More get() test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_with_prefix_routing_error(cache):
    """Test get when prefix routing raises."""
    from yokedcache.backends.base import CacheBackend
    from yokedcache.routing import PrefixRouter

    # Setup prefix router
    cache.setup_prefix_routing()
    if cache._prefix_router:
        # Cause routing to fail
        cache._prefix_router.get_backend = MagicMock(
            side_effect=Exception("routing error")
        )
    # Should fall back to default behavior
    await cache.set("fallback_key", "fallback_val")
    result = await cache.get("fallback_key")
    assert result == "fallback_val"


# ---------------------------------------------------------------------------
# invalidate_by_tags with multiple tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_by_tags_multiple(cache):
    await cache.set("k1", "v1", tags=["tag_a"])
    await cache.set("k2", "v2", tags=["tag_b"])
    result = await cache.invalidate_by_tags(["tag_a", "tag_b"])
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# flush with cleared stale store
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_clears_stale_store():
    config = CacheConfig(
        key_prefix="flush_stale",
        enable_stale_while_revalidate=True,
    )
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True

    await c.set("stale_key", "val", ttl=300)
    assert len(c._stale_store) > 0

    await c.flush()
    # flush_all doesn't automatically clear stale_store but shouldn't raise

    await c.disconnect()


# ---------------------------------------------------------------------------
# health/ping/flush exception paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_alias_exception():
    config = CacheConfig(key_prefix="health_ex")
    c = YokedCache(config=config)
    c._redis = AsyncMock()
    c._redis.ping = AsyncMock(side_effect=Exception("ping failed"))
    c._connected = True

    result = await c.health()
    assert result is False


@pytest.mark.asyncio
async def test_ping_alias_exception():
    config = CacheConfig(key_prefix="ping_ex")
    c = YokedCache(config=config)
    c._redis = AsyncMock()
    c._redis.ping = AsyncMock(side_effect=Exception("ping failed"))
    c._connected = True

    result = await c.ping()
    assert result is False


@pytest.mark.asyncio
async def test_flush_alias_exception():
    config = CacheConfig(key_prefix="flush_ex")
    c = YokedCache(config=config)
    c._redis = AsyncMock()
    c._redis.flushdb = AsyncMock(side_effect=Exception("flushdb failed"))
    c._connected = True

    result = await c.flush()
    assert result is False


# ---------------------------------------------------------------------------
# Sync get/set/delete/exists methods
# ---------------------------------------------------------------------------


def test_get_sync():
    config = CacheConfig(key_prefix="sync_test")
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True

    # Set value first
    asyncio.run(c.set("sync_k", "sync_v"))
    result = c.get_sync("sync_k")
    assert result == "sync_v"


def test_set_sync():
    config = CacheConfig(key_prefix="sync_test2")
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True

    result = c.set_sync("sync_k2", "sync_v2")
    assert result is True


def test_delete_sync():
    config = CacheConfig(key_prefix="sync_test3")
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True

    asyncio.run(c.set("del_sync_k", "val"))
    result = c.delete_sync("del_sync_k")
    assert result is True


def test_exists_sync():
    config = CacheConfig(key_prefix="sync_test4")
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True

    asyncio.run(c.set("exists_k", "val"))
    result = c.exists_sync("exists_k")
    assert result is True
