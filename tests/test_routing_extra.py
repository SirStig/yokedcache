"""Tests for PrefixRouter covering uncovered branches in routing.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from yokedcache.models import CacheEntry, CacheStats, FuzzySearchResult
from yokedcache.routing import PrefixRouter


def _make_result(key, score, term="q"):
    entry = CacheEntry(key=key, value=key, created_at=datetime.now(timezone.utc))
    return FuzzySearchResult(
        key=key, value=key, score=score, matched_term=term, cache_entry=entry
    )


def _make_backend(**overrides):
    """Create a mock async backend."""
    b = AsyncMock()
    for k, v in overrides.items():
        setattr(b, k, v)
    return b


class TestPrefixRouterHealthCheck:
    """Tests for health_check_all."""

    @pytest.mark.asyncio
    async def test_health_check_all_success(self):
        default = _make_backend()
        default.health_check = AsyncMock(return_value=True)
        prefix_b = _make_backend()
        prefix_b.health_check = AsyncMock(return_value=True)

        router = PrefixRouter(default)
        router.add_route("user:", prefix_b)

        results = await router.health_check_all()

        assert results["default"] is True
        assert results["prefix:user:"] is True

    @pytest.mark.asyncio
    async def test_health_check_all_default_fails(self):
        default = _make_backend()
        default.health_check = AsyncMock(side_effect=RuntimeError("conn failed"))
        router = PrefixRouter(default)

        results = await router.health_check_all()
        assert results["default"] is False

    @pytest.mark.asyncio
    async def test_health_check_all_prefix_fails(self):
        default = _make_backend()
        default.health_check = AsyncMock(return_value=True)
        bad = _make_backend()
        bad.health_check = AsyncMock(side_effect=RuntimeError("boom"))
        router = PrefixRouter(default)
        router.add_route("sess:", bad)

        results = await router.health_check_all()
        assert results["default"] is True
        assert results["prefix:sess:"] is False


class TestPrefixRouterExpire:
    """Tests for expire routing."""

    @pytest.mark.asyncio
    async def test_expire_routes_to_correct_backend(self):
        default = _make_backend()
        prefix_b = _make_backend()
        prefix_b.expire = AsyncMock(return_value=True)
        router = PrefixRouter(default)
        router.add_route("cache:", prefix_b)

        result = await router.expire("cache:key1", 120)

        prefix_b.expire.assert_awaited_once_with("cache:key1", 120)
        assert result is True

    @pytest.mark.asyncio
    async def test_expire_falls_back_to_default(self):
        default = _make_backend()
        default.expire = AsyncMock(return_value=False)
        router = PrefixRouter(default)

        result = await router.expire("other:key", 60)
        default.expire.assert_awaited_once_with("other:key", 60)


class TestPrefixRouterInvalidatePattern:
    """Tests for invalidate_pattern covering all-backends fallback."""

    @pytest.mark.asyncio
    async def test_invalidate_pattern_all_backends_when_no_prefix_match(self):
        default = _make_backend()
        default.invalidate_pattern = AsyncMock(return_value=3)
        prefix_b = _make_backend()
        prefix_b.invalidate_pattern = AsyncMock(return_value=2)
        router = PrefixRouter(default)
        router.add_route("user:", prefix_b)

        # Pattern "data:*" doesn't match any prefix, so ALL backends get queried
        count = await router.invalidate_pattern("data:*")

        assert count == 5  # 3 + 2
        default.invalidate_pattern.assert_awaited_once_with("data:*")
        prefix_b.invalidate_pattern.assert_awaited_once_with("data:*")

    @pytest.mark.asyncio
    async def test_invalidate_pattern_exception_is_swallowed(self):
        default = _make_backend()
        default.invalidate_pattern = AsyncMock(side_effect=RuntimeError("oops"))
        router = PrefixRouter(default)

        count = await router.invalidate_pattern("bad:*")
        assert count == 0


class TestPrefixRouterInvalidateTags:
    """Tests for invalidate_tags across all backends."""

    @pytest.mark.asyncio
    async def test_invalidate_tags_all_backends(self):
        default = _make_backend()
        default.invalidate_tags = AsyncMock(return_value=5)
        prefix_b = _make_backend()
        prefix_b.invalidate_tags = AsyncMock(return_value=3)
        router = PrefixRouter(default)
        router.add_route("user:", prefix_b)

        count = await router.invalidate_tags(["tag1", "tag2"])

        assert count == 8
        default.invalidate_tags.assert_awaited_once_with(["tag1", "tag2"])
        prefix_b.invalidate_tags.assert_awaited_once_with(["tag1", "tag2"])

    @pytest.mark.asyncio
    async def test_invalidate_tags_exception_swallowed(self):
        default = _make_backend()
        default.invalidate_tags = AsyncMock(side_effect=RuntimeError("fail"))
        router = PrefixRouter(default)

        count = await router.invalidate_tags("sometag")
        assert count == 0


class TestPrefixRouterFlushAll:
    """Tests for flush_all."""

    @pytest.mark.asyncio
    async def test_flush_all_success(self):
        default = _make_backend()
        default.flush_all = AsyncMock(return_value=True)
        prefix_b = _make_backend()
        prefix_b.flush_all = AsyncMock(return_value=True)
        router = PrefixRouter(default)
        router.add_route("ns:", prefix_b)

        result = await router.flush_all()
        assert result is True

    @pytest.mark.asyncio
    async def test_flush_all_partial_failure(self):
        default = _make_backend()
        default.flush_all = AsyncMock(return_value=True)
        bad = _make_backend()
        bad.flush_all = AsyncMock(side_effect=RuntimeError("fail"))
        router = PrefixRouter(default)
        router.add_route("x:", bad)

        result = await router.flush_all()
        assert result is False

    @pytest.mark.asyncio
    async def test_flush_all_one_returns_false(self):
        default = _make_backend()
        default.flush_all = AsyncMock(return_value=False)
        router = PrefixRouter(default)

        result = await router.flush_all()
        assert result is False


class TestPrefixRouterGetStats:
    """Tests for get_stats."""

    @pytest.mark.asyncio
    async def test_get_stats_all_backends(self):
        default = _make_backend()
        default.get_stats = AsyncMock(return_value=CacheStats(total_hits=10))
        prefix_b = _make_backend()
        prefix_b.get_stats = AsyncMock(return_value=CacheStats(total_hits=5))
        router = PrefixRouter(default)
        router.add_route("ns:", prefix_b)

        stats = await router.get_stats()

        assert "default" in stats
        assert "prefix:ns:" in stats
        assert stats["default"].total_hits == 10
        assert stats["prefix:ns:"].total_hits == 5

    @pytest.mark.asyncio
    async def test_get_stats_default_exception_returns_empty(self):
        default = _make_backend()
        default.get_stats = AsyncMock(side_effect=RuntimeError("oops"))
        router = PrefixRouter(default)

        stats = await router.get_stats()
        assert isinstance(stats["default"], CacheStats)

    @pytest.mark.asyncio
    async def test_get_stats_prefix_exception_returns_empty(self):
        default = _make_backend()
        default.get_stats = AsyncMock(return_value=CacheStats())
        bad = _make_backend()
        bad.get_stats = AsyncMock(side_effect=RuntimeError("fail"))
        router = PrefixRouter(default)
        router.add_route("err:", bad)

        stats = await router.get_stats()
        assert isinstance(stats["prefix:err:"], CacheStats)


class TestPrefixRouterFuzzySearch:
    """Tests for fuzzy_search."""

    @pytest.mark.asyncio
    async def test_fuzzy_search_merges_results(self):
        r1 = _make_result("user:alice", 90, "al")
        r2 = _make_result("user:alan", 85, "al")
        r3 = _make_result("ns:albert", 80, "al")

        default = _make_backend()
        default.fuzzy_search = AsyncMock(return_value=[r1])
        prefix_b = _make_backend()
        prefix_b.fuzzy_search = AsyncMock(return_value=[r2, r3])
        router = PrefixRouter(default)
        router.add_route("ns:", prefix_b)

        results = await router.fuzzy_search("al", threshold=80, max_results=10)

        # Should contain all 3, sorted by score
        assert len(results) == 3
        assert results[0].score == 90

    @pytest.mark.asyncio
    async def test_fuzzy_search_respects_max_results(self):
        results_list = [_make_result(f"k{i}", 90 - i) for i in range(5)]
        default = _make_backend()
        default.fuzzy_search = AsyncMock(return_value=results_list)
        router = PrefixRouter(default)

        results = await router.fuzzy_search("q", max_results=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_fuzzy_search_exception_swallowed(self):
        default = _make_backend()
        default.fuzzy_search = AsyncMock(side_effect=RuntimeError("fail"))
        router = PrefixRouter(default)

        results = await router.fuzzy_search("q")
        assert results == []


class TestPrefixRouterGetAllKeys:
    """Tests for get_all_keys."""

    @pytest.mark.asyncio
    async def test_get_all_keys_deduplicates(self):
        default = _make_backend()
        default.get_all_keys = AsyncMock(return_value=["key1", "key2"])
        prefix_b = _make_backend()
        prefix_b.get_all_keys = AsyncMock(return_value=["key2", "key3"])
        router = PrefixRouter(default)
        router.add_route("ns:", prefix_b)

        keys = await router.get_all_keys("*")
        assert set(keys) == {"key1", "key2", "key3"}

    @pytest.mark.asyncio
    async def test_get_all_keys_exception_swallowed(self):
        default = _make_backend()
        default.get_all_keys = AsyncMock(side_effect=RuntimeError("fail"))
        router = PrefixRouter(default)

        keys = await router.get_all_keys("*")
        assert keys == []


class TestPrefixRouterGetSizeBytes:
    """Tests for get_size_bytes."""

    @pytest.mark.asyncio
    async def test_get_size_bytes_sums_all(self):
        default = _make_backend()
        default.get_size_bytes = AsyncMock(return_value=1024)
        prefix_b = _make_backend()
        prefix_b.get_size_bytes = AsyncMock(return_value=512)
        router = PrefixRouter(default)
        router.add_route("ns:", prefix_b)

        total = await router.get_size_bytes()
        assert total == 1536

    @pytest.mark.asyncio
    async def test_get_size_bytes_exception_skips_backend(self):
        default = _make_backend()
        default.get_size_bytes = AsyncMock(return_value=100)
        bad = _make_backend()
        bad.get_size_bytes = AsyncMock(side_effect=RuntimeError("fail"))
        router = PrefixRouter(default)
        router.add_route("bad:", bad)

        total = await router.get_size_bytes()
        assert total == 100


class TestPrefixRouterConnectDisconnectErrors:
    """Tests for error handling in connect_all and disconnect_all."""

    @pytest.mark.asyncio
    async def test_connect_all_logs_error_on_failure(self):
        default = _make_backend()
        default.connect = AsyncMock(side_effect=RuntimeError("connect failed"))
        router = PrefixRouter(default)

        # Should not raise; just log the error
        await router.connect_all()

    @pytest.mark.asyncio
    async def test_disconnect_all_logs_error_on_failure(self):
        default = _make_backend()
        default.connect = AsyncMock()
        default.disconnect = AsyncMock(side_effect=RuntimeError("disconnect failed"))
        router = PrefixRouter(default)

        await router.connect_all()

        # Should not raise; just log the error
        await router.disconnect_all()
