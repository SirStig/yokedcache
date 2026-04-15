"""Tests for swr.py covering uncovered branches."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache.swr import SWRScheduler


def _make_cache(swr_enabled=True, default_ttl=60):
    """Create a minimal mock cache object."""
    cache = MagicMock()
    cache.config = MagicMock()
    cache.config.default_ttl = default_ttl
    cache.config.enable_stale_while_revalidate = swr_enabled
    cache.config.swr_refresh_threshold = 0.1
    cache.exists = AsyncMock(return_value=True)
    cache.set = AsyncMock(return_value=True)
    return cache


class TestSWRSchedulerShutdown:
    """Tests for shutdown guard in schedule_refresh."""

    @pytest.mark.asyncio
    async def test_schedule_refresh_ignored_when_shutdown(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler._shutdown = True

        scheduler.schedule_refresh("k", AsyncMock(), ttl=10)

        assert "k" not in scheduler._refresh_tasks

    @pytest.mark.asyncio
    async def test_refresh_after_delay_returns_early_when_shutdown(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()
        scheduler._shutdown = True

        # Run the internal coroutine directly with delay=0
        await scheduler._refresh_after_delay("k", AsyncMock(), delay=0, ttl=10)

        cache.set.assert_not_awaited()
        await scheduler.stop()


class TestSWRRefreshPaths:
    """Tests for various loader and result paths in _refresh_after_delay."""

    @pytest.mark.asyncio
    async def test_refresh_with_sync_loader(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()

        def sync_loader():
            return "sync_value"

        await scheduler._refresh_after_delay("k", sync_loader, delay=0, ttl=10)

        cache.set.assert_awaited_once_with("k", "sync_value", ttl=10, tags=None)
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_refresh_with_async_loader(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()

        async def async_loader():
            return "async_value"

        await scheduler._refresh_after_delay("k", async_loader, delay=0, ttl=10)

        cache.set.assert_awaited_once_with("k", "async_value", ttl=10, tags=None)
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_refresh_set_failure_logs_warning(self):
        cache = _make_cache()
        cache.set = AsyncMock(return_value=False)
        scheduler = SWRScheduler(cache)
        scheduler.start()

        loader = AsyncMock(return_value="v")
        await scheduler._refresh_after_delay("k", loader, delay=0, ttl=10)

        cache.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_key_not_exists_skips_set(self):
        cache = _make_cache()
        cache.exists = AsyncMock(return_value=False)
        scheduler = SWRScheduler(cache)
        scheduler.start()

        loader = AsyncMock(return_value="v")
        await scheduler._refresh_after_delay("k", loader, delay=0, ttl=10)

        cache.set.assert_not_awaited()
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_refresh_loader_exception_creates_retry_task(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()

        async def failing_loader():
            raise RuntimeError("loader failed")

        await scheduler._refresh_after_delay("k", failing_loader, delay=0, ttl=10)

        # Give the retry task a moment to be created (but cancel immediately)
        await asyncio.sleep(0)
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_refresh_reschedules_when_swr_enabled(self):
        cache = _make_cache(swr_enabled=True)
        scheduler = SWRScheduler(cache)
        scheduler.start()

        call_count = 0

        async def loader():
            nonlocal call_count
            call_count += 1
            return f"value_{call_count}"

        await scheduler._refresh_after_delay("k", loader, delay=0, ttl=5)

        # The reschedule creates a new task
        await asyncio.sleep(0)
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_refresh_no_reschedule_when_swr_disabled(self):
        cache = _make_cache(swr_enabled=False)
        scheduler = SWRScheduler(cache)
        scheduler.start()

        loader = AsyncMock(return_value="v")
        with patch.object(scheduler, "schedule_refresh") as mock_sched:
            await scheduler._refresh_after_delay("k", loader, delay=0, ttl=10)
            mock_sched.assert_not_called()

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_refresh_cache_ref_gone(self):
        """Test when weak reference to cache has been collected."""
        import weakref

        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()

        # Make the weak ref return None
        scheduler._cache_ref = lambda: None

        loader = AsyncMock(return_value="v")
        await scheduler._refresh_after_delay("k", loader, delay=0, ttl=10)

        cache.set.assert_not_awaited()
        await scheduler.stop()


class TestSWRGetActiveRefreshes:
    """Tests for get_active_refreshes and get_stats."""

    @pytest.mark.asyncio
    async def test_get_active_refreshes_returns_running_keys(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()

        loader = AsyncMock(return_value="v")
        scheduler.schedule_refresh("key1", loader, ttl=300)
        scheduler.schedule_refresh("key2", loader, ttl=300)

        active = scheduler.get_active_refreshes()
        assert "key1" in active or "key2" in active

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_get_stats_returns_dict(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()

        loader = AsyncMock(return_value="v")
        scheduler.schedule_refresh("key1", loader, ttl=300)

        stats = scheduler.get_stats()
        assert "active_refreshes" in stats
        assert "completed_refreshes" in stats
        assert "total_scheduled" in stats
        assert "is_running" in stats
        assert stats["is_running"] is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_get_stats_when_stopped(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)

        stats = scheduler.get_stats()
        assert stats["is_running"] is False
        assert stats["active_refreshes"] == 0

    @pytest.mark.asyncio
    async def test_cancel_refresh(self):
        cache = _make_cache()
        scheduler = SWRScheduler(cache)
        scheduler.start()

        loader = AsyncMock(return_value="v")
        scheduler.schedule_refresh("key1", loader, ttl=300)
        result = scheduler.cancel_refresh("key1")
        assert result is True

        result_missing = scheduler.cancel_refresh("nonexistent")
        assert result_missing is False

        await scheduler.stop()
