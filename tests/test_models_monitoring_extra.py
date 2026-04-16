"""
Tests for uncovered paths in models.py and monitoring.py.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache.models import CacheEntry, CacheStats, InvalidationRule, InvalidationType

# ===========================================================================
# MODELS
# ===========================================================================

# ---------------------------------------------------------------------------
# CacheEntry.is_expired
# ---------------------------------------------------------------------------


def test_cache_entry_is_expired_past():
    entry = CacheEntry(
        key="k",
        value="v",
        created_at=datetime.utcnow() - timedelta(hours=1),
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    assert entry.is_expired is True


def test_cache_entry_is_expired_future():
    entry = CacheEntry(
        key="k",
        value="v",
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    assert entry.is_expired is False


def test_cache_entry_is_expired_none():
    entry = CacheEntry(key="k", value="v", created_at=datetime.utcnow())
    assert entry.is_expired is False


# ---------------------------------------------------------------------------
# CacheEntry.age_seconds
# ---------------------------------------------------------------------------


def test_cache_entry_age_seconds():
    created = datetime.utcnow() - timedelta(seconds=5)
    entry = CacheEntry(key="k", value="v", created_at=created)
    age = entry.age_seconds
    assert age >= 4.9


# ---------------------------------------------------------------------------
# CacheEntry.touch
# ---------------------------------------------------------------------------


def test_cache_entry_touch():
    entry = CacheEntry(key="k", value="v", created_at=datetime.utcnow())
    assert entry.hit_count == 0
    assert entry.last_accessed is None

    entry.touch()
    assert entry.hit_count == 1
    assert entry.last_accessed is not None

    entry.touch()
    assert entry.hit_count == 2


# ---------------------------------------------------------------------------
# CacheStats.add_hit with table and tags
# ---------------------------------------------------------------------------


def test_cache_stats_add_hit_with_table_and_tags():
    stats = CacheStats()
    stats.add_hit(table="users", tags={"t1"})

    assert stats.total_hits == 1
    assert "users" in stats.table_stats
    assert stats.table_stats["users"]["hits"] == 1
    assert "t1" in stats.tag_stats
    assert stats.tag_stats["t1"]["hits"] == 1


# ---------------------------------------------------------------------------
# CacheStats.add_miss with table and tags
# ---------------------------------------------------------------------------


def test_cache_stats_add_miss_with_table_and_tags():
    stats = CacheStats()
    stats.add_miss(table="users", tags={"t1"})

    assert stats.total_misses == 1
    assert stats.table_stats["users"]["misses"] == 1
    assert stats.tag_stats["t1"]["misses"] == 1


# ---------------------------------------------------------------------------
# CacheStats._update_table_stats and _update_tag_stats (multiple calls)
# ---------------------------------------------------------------------------


def test_cache_stats_update_table_stats_multiple():
    stats = CacheStats()
    stats._update_table_stats("orders", "hits")
    stats._update_table_stats("orders", "hits")
    stats._update_table_stats("orders", "misses")
    assert stats.table_stats["orders"]["hits"] == 2
    assert stats.table_stats["orders"]["misses"] == 1


def test_cache_stats_update_tag_stats_multiple():
    stats = CacheStats()
    stats._update_tag_stats("product", "sets")
    stats._update_tag_stats("product", "deletes")
    assert stats.tag_stats["product"]["sets"] == 1
    assert stats.tag_stats["product"]["deletes"] == 1


# ---------------------------------------------------------------------------
# InvalidationRule.should_invalidate
# ---------------------------------------------------------------------------


def test_invalidation_rule_should_invalidate_true():
    rule = InvalidationRule(
        table_name="users",
        invalidation_types={InvalidationType.INSERT, InvalidationType.UPDATE},
    )
    assert rule.should_invalidate(InvalidationType.INSERT) is True
    assert rule.should_invalidate(InvalidationType.UPDATE) is True


def test_invalidation_rule_should_invalidate_false():
    rule = InvalidationRule(
        table_name="users",
        invalidation_types={InvalidationType.INSERT},
    )
    assert rule.should_invalidate(InvalidationType.DELETE) is False


# ===========================================================================
# MONITORING
# ===========================================================================

# ---------------------------------------------------------------------------
# PrometheusCollector when available
# ---------------------------------------------------------------------------


def _make_prometheus_collector():
    """Create a PrometheusCollector with mocked prometheus_client."""
    from unittest.mock import MagicMock, patch

    with (
        patch("prometheus_client.Counter") as mock_counter_class,
        patch("prometheus_client.Gauge") as mock_gauge_class,
        patch("prometheus_client.Histogram") as mock_histogram_class,
        patch("prometheus_client.REGISTRY"),
    ):
        from yokedcache.monitoring import PrometheusCollector

        collector = PrometheusCollector()
        # Set up mock objects for assertions
        collector._get_counter = MagicMock()
        collector._set_counter = MagicMock()
        collector._delete_counter = MagicMock()
        collector._invalidation_counter = MagicMock()
        collector._cache_size_gauge = MagicMock()
        collector._cache_keys_gauge = MagicMock()
        collector._hit_rate_gauge = MagicMock()
        collector._operation_duration = MagicMock()
        collector.available = True
        return collector


def test_prometheus_collector_increment():
    try:
        import prometheus_client
    except ImportError:
        pytest.skip("prometheus_client not available")

    with (
        patch("prometheus_client.Counter"),
        patch("prometheus_client.Gauge"),
        patch("prometheus_client.Histogram"),
        patch("prometheus_client.REGISTRY"),
    ):
        from yokedcache.monitoring import PrometheusCollector

        collector = PrometheusCollector()
        collector._get_counter = MagicMock()
        collector._set_counter = MagicMock()
        collector._delete_counter = MagicMock()
        collector._invalidation_counter = MagicMock()
        collector.available = True

        asyncio.run(collector.increment("cache.gets", tags={"result": "hit"}))
        asyncio.run(collector.increment("cache.sets"))
        asyncio.run(collector.increment("cache.deletes"))
        asyncio.run(
            collector.increment("cache.invalidations", tags={"type": "pattern"})
        )
        collector._get_counter.labels.assert_called()


def test_prometheus_collector_gauge():
    try:
        import prometheus_client
    except ImportError:
        pytest.skip("prometheus_client not available")

    with (
        patch("prometheus_client.Counter"),
        patch("prometheus_client.Gauge"),
        patch("prometheus_client.Histogram"),
        patch("prometheus_client.REGISTRY"),
    ):
        from yokedcache.monitoring import PrometheusCollector

        collector = PrometheusCollector()
        collector._cache_size_gauge = MagicMock()
        collector._cache_keys_gauge = MagicMock()
        collector._hit_rate_gauge = MagicMock()
        collector.available = True

        asyncio.run(collector.gauge("cache.size_bytes", 1024))
        asyncio.run(collector.gauge("cache.keys_total", 100))
        asyncio.run(collector.gauge("cache.hit_rate", 0.85))
        collector._cache_size_gauge.set.assert_called_with(1024)


def test_prometheus_collector_histogram():
    try:
        import prometheus_client
    except ImportError:
        pytest.skip("prometheus_client not available")

    with (
        patch("prometheus_client.Counter"),
        patch("prometheus_client.Gauge"),
        patch("prometheus_client.Histogram"),
        patch("prometheus_client.REGISTRY"),
    ):
        from yokedcache.monitoring import PrometheusCollector

        collector = PrometheusCollector()
        collector._operation_duration = MagicMock()
        collector.available = True

        asyncio.run(
            collector.histogram(
                "cache.operation_duration", 0.05, tags={"operation": "get"}
            )
        )
        collector._operation_duration.labels.assert_called()


def test_prometheus_collector_timing():
    try:
        import prometheus_client
    except ImportError:
        pytest.skip("prometheus_client not available")

    with (
        patch("prometheus_client.Counter"),
        patch("prometheus_client.Gauge"),
        patch("prometheus_client.Histogram"),
        patch("prometheus_client.REGISTRY"),
    ):
        from yokedcache.monitoring import PrometheusCollector

        collector = PrometheusCollector()
        collector._operation_duration = MagicMock()
        collector.available = True

        asyncio.run(
            collector.timing(
                "cache.operation_duration", 0.03, tags={"operation": "set"}
            )
        )
        collector._operation_duration.labels.assert_called()


# ---------------------------------------------------------------------------
# StatsDCollector when available
# ---------------------------------------------------------------------------


def _make_statsd_collector():
    """Create a StatsDCollector with mocked statsd."""
    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.increment = MagicMock()
        mock_client.gauge = MagicMock()
        mock_client.histogram = MagicMock()
        mock_client.timing = MagicMock()
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client
        return collector


def test_statsd_collector_increment():
    try:
        import statsd
    except ImportError:
        pytest.skip("statsd not available")

    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        asyncio.run(collector.increment("cache.gets", tags={"result": "hit"}))
        mock_client.increment.assert_called()


def test_statsd_collector_gauge():
    try:
        import statsd
    except ImportError:
        pytest.skip("statsd not available")

    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        asyncio.run(collector.gauge("cache.size_bytes", 2048))
        mock_client.gauge.assert_called()


def test_statsd_collector_histogram():
    try:
        import statsd
    except ImportError:
        pytest.skip("statsd not available")

    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        asyncio.run(collector.histogram("cache.op_duration", 0.1))
        mock_client.histogram.assert_called()


def test_statsd_collector_timing():
    try:
        import statsd
    except ImportError:
        pytest.skip("statsd not available")

    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        asyncio.run(collector.timing("cache.op_duration", 0.05))
        mock_client.timing.assert_called()


# ---------------------------------------------------------------------------
# CacheMetrics (monitoring.py) with failing collector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitoring_cache_metrics_collector_gauge_exception():
    from yokedcache.monitoring import CacheMetrics

    bad_collector = MagicMock()
    bad_collector.gauge = AsyncMock(side_effect=Exception("gauge failed"))
    bad_collector.histogram = AsyncMock(side_effect=Exception("histogram failed"))
    bad_collector.timing = AsyncMock(side_effect=Exception("timing failed"))

    metrics = CacheMetrics(collectors=[bad_collector])

    # Should not raise
    await metrics.gauge("cache.size_bytes", 100)
    await metrics.histogram("cache.op", 0.1)
    await metrics.timing("cache.op", 0.1)


@pytest.mark.asyncio
async def test_monitoring_cache_metrics_collector_increment_exception():
    from yokedcache.monitoring import CacheMetrics

    bad_collector = MagicMock()
    bad_collector.increment = AsyncMock(side_effect=Exception("increment failed"))

    metrics = CacheMetrics(collectors=[bad_collector])

    # Should not raise
    await metrics.increment("cache.gets")


# ---------------------------------------------------------------------------
# PrometheusCollector when not available (lines 146, 168, 186)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prometheus_collector_not_available():
    """Test PrometheusCollector methods when available=False."""
    from yokedcache.monitoring import PrometheusCollector

    # Create with unavailable state by patching prometheus_client to fail
    with patch.dict("sys.modules", {"prometheus_client": None}):
        collector = PrometheusCollector()

    assert collector.available is False
    # Should early-return without error
    await collector.increment("cache.gets")
    await collector.gauge("cache.size_bytes", 100)
    await collector.histogram("cache.op", 0.1)
    await collector.timing("cache.op", 0.1)


# ---------------------------------------------------------------------------
# StatsDCollector when not available (lines 249, 265, 281, 297)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_statsd_collector_not_available():
    """Test StatsDCollector methods when available=False."""
    from yokedcache.monitoring import StatsDCollector

    with patch.dict("sys.modules", {"statsd": None}):
        collector = StatsDCollector()

    assert collector.available is False
    # Should early-return without error
    await collector.increment("cache.gets")
    await collector.gauge("cache.size_bytes", 100)
    await collector.histogram("cache.op", 0.1)
    await collector.timing("cache.op", 0.1)


# ---------------------------------------------------------------------------
# StatsDCollector exception paths (lines 270-271, 286-287, 302-303)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_statsd_collector_gauge_exception():
    try:
        import statsd
    except ImportError:
        pytest.skip("statsd not available")

    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.gauge = MagicMock(side_effect=Exception("gauge error"))
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        # Should not raise, just log debug
        await collector.gauge("cache.size_bytes", 100)


@pytest.mark.asyncio
async def test_statsd_collector_histogram_exception():
    try:
        import statsd
    except ImportError:
        pytest.skip("statsd not available")

    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.histogram = MagicMock(side_effect=Exception("histogram error"))
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        await collector.histogram("cache.op", 0.1)


@pytest.mark.asyncio
async def test_statsd_collector_timing_exception():
    try:
        import statsd
    except ImportError:
        pytest.skip("statsd not available")

    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.timing = MagicMock(side_effect=Exception("timing error"))
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        await collector.timing("cache.op", 0.1)
