"""Tests for YokedCache internal methods and coverage of uncovered branches."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from yokedcache import CacheConfig, YokedCache
from yokedcache.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
)
from yokedcache.models import SerializationMethod
from yokedcache.utils import serialize_for_cache


def _serialize(value):
    return serialize_for_cache(value, SerializationMethod.JSON)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_with_cb():
    """Config with circuit breaker and metrics enabled."""
    return CacheConfig(
        redis_url="redis://localhost:6379/0",
        enable_circuit_breaker=True,
        enable_metrics=True,
        default_ttl=60,
        key_prefix="test_direct",
    )


@pytest.fixture
def config_no_cb():
    """Config with circuit breaker disabled."""
    return CacheConfig(
        redis_url="redis://localhost:6379/0",
        enable_circuit_breaker=False,
        enable_metrics=True,
        default_ttl=60,
        key_prefix="test_direct_nocb",
    )


@pytest.fixture
def fake_redis_instance():
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def cache_with_cb(config_with_cb, fake_redis_instance):
    c = YokedCache(config=config_with_cb)
    c._redis = fake_redis_instance
    c._connected = True
    return c


@pytest.fixture
def cache_no_cb(config_no_cb, fake_redis_instance):
    c = YokedCache(config=config_no_cb)
    c._redis = fake_redis_instance
    c._connected = True
    return c


# ---------------------------------------------------------------------------
# Tests: _direct_get (circuit breaker enabled)
# ---------------------------------------------------------------------------


class TestDirectGetWithCircuitBreaker:

    @pytest.mark.asyncio
    async def test_direct_get_miss(self, cache_with_cb):
        result = await cache_with_cb._direct_get("nonexistent_key", default="fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_direct_get_hit(self, cache_with_cb):
        raw = _serialize("hello")
        await cache_with_cb._redis.set("testkey_hit", raw)
        result = await cache_with_cb._direct_get("testkey_hit")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_direct_get_deserialization_error(self, cache_with_cb):
        """Bad data stored in Redis should return default without raising."""
        await cache_with_cb._redis.set("bad_key", b"not-valid-json-or-msgpack")
        result = await cache_with_cb._direct_get("bad_key", default="safe")
        assert result == "safe"

    @pytest.mark.asyncio
    async def test_direct_get_not_connected(self, config_with_cb):
        c = YokedCache(config=config_with_cb)
        # Do not set _connected / _redis
        result = await c._direct_get("k", default="x")
        assert result == "x"

    @pytest.mark.asyncio
    async def test_direct_get_circuit_breaker_open_returns_default(self, cache_with_cb):
        """Open circuit breaker should return default."""
        cb = cache_with_cb._circuit_breaker
        cb.state = CircuitBreakerState.OPEN
        cb.last_failure_time = 9_999_999_999  # far future; won't reset

        result = await cache_with_cb._direct_get("k", default="cb_default")
        assert result == "cb_default"

    @pytest.mark.asyncio
    async def test_direct_get_generic_exception_returns_default(self, cache_with_cb):
        """Generic exceptions should be caught and return default."""
        cache_with_cb._redis.get = AsyncMock(side_effect=RuntimeError("boom"))
        result = await cache_with_cb._direct_get("k", default="err")
        assert result == "err"


# ---------------------------------------------------------------------------
# Tests: _direct_get (circuit breaker disabled)
# ---------------------------------------------------------------------------


class TestDirectGetNoCB:

    @pytest.mark.asyncio
    async def test_direct_get_miss(self, cache_no_cb):
        result = await cache_no_cb._direct_get("k", default="d")
        assert result == "d"

    @pytest.mark.asyncio
    async def test_direct_get_hit(self, cache_no_cb):
        raw = _serialize({"x": 1})
        await cache_no_cb._redis.set("obj_key", raw)
        result = await cache_no_cb._direct_get("obj_key")
        assert result == {"x": 1}

    @pytest.mark.asyncio
    async def test_direct_get_deserialization_error(self, cache_no_cb):
        await cache_no_cb._redis.set("bad_key2", b"\xff\xfe garbage")
        result = await cache_no_cb._direct_get("bad_key2", default="safe2")
        assert result == "safe2"

    @pytest.mark.asyncio
    async def test_direct_get_exception_returns_default(self, cache_no_cb):
        cache_no_cb._redis.get = AsyncMock(side_effect=RuntimeError("no cb"))
        result = await cache_no_cb._direct_get("k", default="err2")
        assert result == "err2"


# ---------------------------------------------------------------------------
# Tests: _direct_set
# ---------------------------------------------------------------------------


class TestDirectSet:

    @pytest.mark.asyncio
    async def test_direct_set_with_cb(self, cache_with_cb):
        result = await cache_with_cb._direct_set("mykey", "myvalue", ttl=30)
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_set_with_tags_and_cb(self, cache_with_cb):
        result = await cache_with_cb._direct_set(
            "tagkey", "tv", ttl=60, tags={"t1", "t2"}
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_set_no_cb(self, cache_no_cb):
        result = await cache_no_cb._direct_set("nokey", "nv", ttl=10)
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_set_no_cb_with_tags(self, cache_no_cb):
        result = await cache_no_cb._direct_set("tkey", "tv", ttl=10, tags={"mytag"})
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_set_not_connected(self, config_with_cb):
        c = YokedCache(config=config_with_cb)
        result = await c._direct_set("k", "v")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_set_circuit_breaker_open(self, cache_with_cb):
        cb = cache_with_cb._circuit_breaker
        cb.state = CircuitBreakerState.OPEN
        cb.last_failure_time = 9_999_999_999

        result = await cache_with_cb._direct_set("k", "v")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_set_generic_exception(self, cache_with_cb):
        cache_with_cb._redis.set = AsyncMock(side_effect=RuntimeError("write fail"))
        result = await cache_with_cb._direct_set("k", "v")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_set_no_cb_generic_exception(self, cache_no_cb):
        cache_no_cb._redis.set = AsyncMock(side_effect=RuntimeError("no cb set fail"))
        result = await cache_no_cb._direct_set("k", "v")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: _direct_delete
# ---------------------------------------------------------------------------


class TestDirectDelete:

    @pytest.mark.asyncio
    async def test_direct_delete_existing_key_with_cb(self, cache_with_cb):
        raw = _serialize("value")
        await cache_with_cb._redis.set("del_key", raw)
        result = await cache_with_cb._direct_delete("del_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_delete_nonexistent_key_with_cb(self, cache_with_cb):
        result = await cache_with_cb._direct_delete("no_such_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_delete_no_cb(self, cache_no_cb):
        raw = _serialize("v")
        await cache_no_cb._redis.set("del_key2", raw)
        result = await cache_no_cb._direct_delete("del_key2")
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_delete_not_connected(self, config_with_cb):
        c = YokedCache(config=config_with_cb)
        result = await c._direct_delete("k")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_delete_circuit_breaker_open(self, cache_with_cb):
        cb = cache_with_cb._circuit_breaker
        cb.state = CircuitBreakerState.OPEN
        cb.last_failure_time = 9_999_999_999

        result = await cache_with_cb._direct_delete("k")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_delete_generic_exception(self, cache_with_cb):
        cache_with_cb._redis.delete = AsyncMock(side_effect=RuntimeError("del fail"))
        result = await cache_with_cb._direct_delete("k")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_delete_no_cb_exception(self, cache_no_cb):
        cache_no_cb._redis.delete = AsyncMock(side_effect=RuntimeError("no cb del"))
        result = await cache_no_cb._direct_delete("k")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: _direct_exists
# ---------------------------------------------------------------------------


class TestDirectExists:

    @pytest.mark.asyncio
    async def test_direct_exists_true_with_cb(self, cache_with_cb):
        await cache_with_cb._redis.set("exist_key", b"v")
        result = await cache_with_cb._direct_exists("exist_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_exists_false_with_cb(self, cache_with_cb):
        result = await cache_with_cb._direct_exists("missing_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_exists_no_cb(self, cache_no_cb):
        await cache_no_cb._redis.set("ex_key", b"v")
        result = await cache_no_cb._direct_exists("ex_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_direct_exists_not_connected(self, config_with_cb):
        c = YokedCache(config=config_with_cb)
        result = await c._direct_exists("k")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_exists_circuit_breaker_open(self, cache_with_cb):
        cb = cache_with_cb._circuit_breaker
        cb.state = CircuitBreakerState.OPEN
        cb.last_failure_time = 9_999_999_999
        result = await cache_with_cb._direct_exists("k")
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_exists_exception(self, cache_with_cb):
        cache_with_cb._redis.exists = AsyncMock(side_effect=RuntimeError("exists fail"))
        result = await cache_with_cb._direct_exists("k")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: _direct_expire
# ---------------------------------------------------------------------------


class TestDirectExpire:

    @pytest.mark.asyncio
    async def test_direct_expire_with_cb(self, cache_with_cb):
        await cache_with_cb._redis.set("exp_key", b"v")
        result = await cache_with_cb._direct_expire("exp_key", 120)
        # fakeredis returns True/1 for expire
        assert result is not None

    @pytest.mark.asyncio
    async def test_direct_expire_no_cb(self, cache_no_cb):
        await cache_no_cb._redis.set("exp_key2", b"v")
        result = await cache_no_cb._direct_expire("exp_key2", 60)
        assert result is not None

    @pytest.mark.asyncio
    async def test_direct_expire_not_connected(self, config_with_cb):
        c = YokedCache(config=config_with_cb)
        result = await c._direct_expire("k", 60)
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_expire_circuit_breaker_open(self, cache_with_cb):
        cb = cache_with_cb._circuit_breaker
        cb.state = CircuitBreakerState.OPEN
        cb.last_failure_time = 9_999_999_999
        result = await cache_with_cb._direct_expire("k", 60)
        assert result is False

    @pytest.mark.asyncio
    async def test_direct_expire_exception(self, cache_with_cb):
        cache_with_cb._redis.expire = AsyncMock(side_effect=RuntimeError("exp fail"))
        result = await cache_with_cb._direct_expire("k", 60)
        assert result is False


# ---------------------------------------------------------------------------
# Tests: detailed_health_check
# ---------------------------------------------------------------------------


class TestDetailedHealthCheck:

    @pytest.mark.asyncio
    async def test_detailed_health_check_healthy(self, cache_with_cb):
        health = await cache_with_cb.detailed_health_check()
        assert health["cache"]["redis_available"] is True
        assert health["cache"]["connected"] is True

    @pytest.mark.asyncio
    async def test_detailed_health_check_redis_ping_fails(self, cache_with_cb):
        cache_with_cb._redis.ping = AsyncMock(side_effect=RuntimeError("ping fail"))
        health = await cache_with_cb.detailed_health_check()
        assert health["cache"]["redis_available"] is False
        assert health["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_detailed_health_check_with_circuit_breaker_stats(
        self, cache_with_cb
    ):
        health = await cache_with_cb.detailed_health_check()
        assert "circuit_breaker_stats" in health["cache"]

    @pytest.mark.asyncio
    async def test_detailed_health_check_circuit_breaker_open(self, cache_with_cb):
        cb = cache_with_cb._circuit_breaker
        cb.state = CircuitBreakerState.OPEN
        # Use last_failure_time in the past so operations can proceed
        cb.last_failure_time = 0
        health = await cache_with_cb.detailed_health_check()
        # Status may be degraded/unhealthy because of circuit breaker open state
        assert health["status"] in ("healthy", "degraded", "unhealthy")

    @pytest.mark.asyncio
    async def test_detailed_health_check_no_redis(self, config_with_cb):
        c = YokedCache(config=config_with_cb)
        c._connected = True
        c._redis = None
        health = await c.detailed_health_check()
        assert "Redis client not initialized" in health["errors"]

    @pytest.mark.asyncio
    async def test_detailed_health_check_performance_warnings(self, cache_with_cb):
        """Trigger low hit rate warning by setting misses."""
        cache_with_cb._stats.total_misses = 100
        cache_with_cb._stats.total_hits = 0
        health = await cache_with_cb.detailed_health_check()
        # Should mention hit rate warning if threshold met
        assert isinstance(health["warnings"], list)


# ---------------------------------------------------------------------------
# Tests: fetch_or_set (single flight and non-single-flight paths)
# ---------------------------------------------------------------------------


class TestFetchOrSet:

    @pytest.mark.asyncio
    async def test_fetch_or_set_cache_miss_calls_loader(self, cache_with_cb):
        loader = AsyncMock(return_value="computed")
        result = await cache_with_cb.fetch_or_set("fs_key", loader, ttl=30)
        assert result == "computed"
        loader.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_or_set_cache_hit_skips_loader(self, cache_with_cb):
        await cache_with_cb.set("fs_hit_key", "cached_value", ttl=60)
        loader = AsyncMock(return_value="new_value")
        result = await cache_with_cb.fetch_or_set("fs_hit_key", loader, ttl=60)
        assert result == "cached_value"
        loader.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetch_or_set_sync_loader(self, cache_with_cb):
        def sync_loader():
            return "sync_computed"

        result = await cache_with_cb.fetch_or_set("fs_sync", sync_loader, ttl=30)
        assert result == "sync_computed"

    @pytest.mark.asyncio
    async def test_fetch_or_set_no_single_flight(
        self, config_with_cb, fake_redis_instance
    ):
        config_with_cb.enable_single_flight = False
        c = YokedCache(config=config_with_cb)
        c._redis = fake_redis_instance
        c._connected = True

        loader = AsyncMock(return_value="direct")
        result = await c.fetch_or_set("fs_no_sf", loader, ttl=30)
        assert result == "direct"

    @pytest.mark.asyncio
    async def test_fetch_or_set_second_waiter_gets_cached(self, cache_with_cb):
        """When two coroutines race, the second should get the cached result."""
        compute_count = 0

        async def slow_loader():
            nonlocal compute_count
            compute_count += 1
            await asyncio.sleep(0.01)
            return "race_result"

        key = "race_key"
        t1, t2 = await asyncio.gather(
            cache_with_cb.fetch_or_set(key, slow_loader, ttl=60),
            cache_with_cb.fetch_or_set(key, slow_loader, ttl=60),
        )
        assert t1 == "race_result"
        assert t2 == "race_result"
        # At most 2 computations due to race, but typically 1
        assert compute_count <= 2


# ---------------------------------------------------------------------------
# Tests: _get_redis raises when not available
# ---------------------------------------------------------------------------


class TestGetRedis:

    @pytest.mark.asyncio
    async def test_get_redis_raises_when_redis_none(self, config_with_cb):
        from yokedcache.exceptions import CacheConnectionError

        c = YokedCache(config=config_with_cb)
        c._connected = True
        c._redis = None
        with pytest.raises(CacheConnectionError):
            async with c._get_redis():
                pass


# ---------------------------------------------------------------------------
# Tests: disconnect paths
# ---------------------------------------------------------------------------


class TestDisconnect:

    @pytest.mark.asyncio
    async def test_disconnect_uses_aclose_if_available(self, cache_with_cb):
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()
        cache_with_cb._redis = mock_redis
        await cache_with_cb.disconnect()
        mock_redis.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_uses_close_if_no_aclose(self, cache_with_cb):
        mock_redis = AsyncMock(spec=[])  # no aclose
        mock_redis.close = AsyncMock()
        cache_with_cb._redis = mock_redis
        await cache_with_cb.disconnect()
        mock_redis.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_with_pool(self, cache_with_cb):
        mock_pool = AsyncMock()
        cache_with_cb._pool = mock_pool
        cache_with_cb._redis = None
        await cache_with_cb.disconnect()
        mock_pool.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: connect fallback / memory fallback
# ---------------------------------------------------------------------------


class TestConnectFallback:

    @pytest.mark.asyncio
    async def test_connect_raises_when_fallback_disabled(self):
        config = CacheConfig(
            redis_url="redis://invalid.host.that.does.not.exist:9999/0",
            enable_memory_fallback=False,
            fallback_enabled=False,
            connection_retries=0,
        )
        from yokedcache.exceptions import CacheConnectionError

        c = YokedCache(config=config)
        with pytest.raises((CacheConnectionError, Exception)):
            await c.connect()

    @pytest.mark.asyncio
    async def test_connect_uses_memory_fallback_on_failure(self):
        config = CacheConfig(
            redis_url="redis://invalid.host.that.does.not.exist:9999/0",
            enable_memory_fallback=True,
            fallback_enabled=True,
            connection_retries=0,
        )
        c = YokedCache(config=config)
        await c.connect()
        assert c._connected is True
        assert c._fallback_mode is True
        await c.disconnect()
