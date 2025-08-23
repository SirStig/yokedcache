"""
Tests for monitoring and metrics functionality.

This module tests Prometheus, StatsD, and general metrics collection features.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from yokedcache.monitoring import CacheMetrics, NoOpCollector


class TestNoOpCollector:
    """Test the no-operation metrics collector."""

    @pytest.mark.asyncio
    async def test_noop_collector_methods(self):
        """Test that NoOpCollector methods do nothing."""
        collector = NoOpCollector()

        # All methods should complete without error
        await collector.increment("test_metric", 1, {"tag": "value"})
        await collector.gauge("test_metric", 100.0, {"tag": "value"})
        await collector.histogram("test_metric", 0.5, {"tag": "value"})
        await collector.timing("test_metric", 1.0, {"tag": "value"})

        # No exceptions should be raised


class TestCacheMetrics:
    """Test the cache metrics wrapper."""

    @pytest.fixture
    def mock_collector(self):
        """Create a mock metrics collector."""
        collector = Mock()
        collector.increment = AsyncMock()
        collector.gauge = AsyncMock()
        collector.histogram = AsyncMock()
        collector.timing = AsyncMock()
        return collector

    def test_cache_metrics_initialization(self):
        """Test CacheMetrics initialization."""
        # Default initialization should use NoOpCollector
        metrics = CacheMetrics()
        assert len(metrics.collectors) == 1
        assert isinstance(metrics.collectors[0], NoOpCollector)

        # Initialize with specific collectors
        mock_collector = Mock()
        metrics = CacheMetrics([mock_collector])
        assert len(metrics.collectors) == 1
        assert metrics.collectors[0] == mock_collector

    def test_add_collector(self, mock_collector):
        """Test adding collectors to CacheMetrics."""
        metrics = CacheMetrics()

        # Adding first real collector should replace NoOpCollector
        metrics.add_collector(mock_collector)
        assert len(metrics.collectors) == 1
        assert metrics.collectors[0] == mock_collector

        # Adding second collector should append
        mock_collector2 = Mock()
        metrics.add_collector(mock_collector2)
        assert len(metrics.collectors) == 2
        assert mock_collector2 in metrics.collectors

    @pytest.mark.asyncio
    async def test_cache_metrics_increment(self, mock_collector):
        """Test increment method delegation."""
        metrics = CacheMetrics([mock_collector])

        await metrics.increment("test_metric", 5, {"tag": "value"})

        mock_collector.increment.assert_called_once_with(
            "test_metric", 5, {"tag": "value"}
        )

    @pytest.mark.asyncio
    async def test_cache_metrics_gauge(self, mock_collector):
        """Test gauge method delegation."""
        metrics = CacheMetrics([mock_collector])

        await metrics.gauge("test_metric", 100.0, {"tag": "value"})

        mock_collector.gauge.assert_called_once_with(
            "test_metric", 100.0, {"tag": "value"}
        )

    @pytest.mark.asyncio
    async def test_cache_metrics_histogram(self, mock_collector):
        """Test histogram method delegation."""
        metrics = CacheMetrics([mock_collector])

        await metrics.histogram("test_metric", 0.5, {"tag": "value"})

        mock_collector.histogram.assert_called_once_with(
            "test_metric", 0.5, {"tag": "value"}
        )

    @pytest.mark.asyncio
    async def test_cache_metrics_timing(self, mock_collector):
        """Test timing method delegation."""
        metrics = CacheMetrics([mock_collector])

        await metrics.timing("test_metric", 1.5, {"tag": "value"})

        mock_collector.timing.assert_called_once_with(
            "test_metric", 1.5, {"tag": "value"}
        )

    @pytest.mark.asyncio
    async def test_cache_metrics_error_handling(self):
        """Test error handling in metrics collection."""
        # Create a collector that raises errors
        error_collector = Mock()
        error_collector.increment = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = CacheMetrics([error_collector])

        # Should not raise exception
        await metrics.increment("test_metric", 1)

    @pytest.mark.asyncio
    async def test_timer_functionality(self, mock_collector):
        """Test timer start/end functionality."""
        metrics = CacheMetrics([mock_collector])

        # Start timer
        timer_id = metrics.start_timer("test_operation")
        assert timer_id.startswith("test_operation_")
        assert timer_id in metrics._operation_start_times

        # End timer
        await metrics.end_timer(timer_id, "test_operation")

        # Should have called timing method
        mock_collector.timing.assert_called_once()
        call_args = mock_collector.timing.call_args
        assert call_args[0][0] == "cache.operation_duration"
        assert isinstance(call_args[0][1], float)
        assert call_args[0][2] == {"operation": "test_operation"}

        # Timer should be removed
        assert timer_id not in metrics._operation_start_times


@pytest.mark.skipif(
    not pytest.importorskip(
        "prometheus_client", reason="prometheus_client not available"
    ),
    reason="Prometheus client not available",
)
class TestPrometheusCollector:
    """Test Prometheus metrics collector."""

    def test_prometheus_collector_initialization(self):
        """Test PrometheusCollector initialization."""
        from yokedcache.monitoring import PrometheusCollector

        with (
            patch("prometheus_client.Counter"),
            patch("prometheus_client.Gauge"),
            patch("prometheus_client.Histogram"),
            patch("prometheus_client.Summary"),
            patch("prometheus_client.REGISTRY"),
        ):

            collector = PrometheusCollector(namespace="test")
            assert collector.namespace == "test"
            assert collector.available is True

    def test_prometheus_collector_without_dependencies(self):
        """Test PrometheusCollector when prometheus_client is not available."""
        with patch.dict("sys.modules", {"prometheus_client": None}):
            from yokedcache.monitoring import PrometheusCollector

            collector = PrometheusCollector()
            assert collector.available is False

    @pytest.mark.asyncio
    async def test_prometheus_collector_increment(self):
        """Test Prometheus increment functionality."""
        from yokedcache.monitoring import PrometheusCollector

        with (
            patch("prometheus_client.Counter") as mock_counter_class,
            patch("prometheus_client.Gauge"),
            patch("prometheus_client.Histogram"),
            patch("prometheus_client.Summary"),
            patch("prometheus_client.REGISTRY"),
        ):

            mock_counter = Mock()
            mock_counter.labels.return_value.inc = Mock()
            mock_counter.inc = Mock()
            mock_counter_class.return_value = mock_counter

            collector = PrometheusCollector()
            collector._get_counter = mock_counter
            collector._set_counter = mock_counter

            # Test cache.gets metric
            await collector.increment("cache.gets", 1, {"result": "hit"})
            mock_counter.labels.assert_called_with(result="hit")

            # Test cache.sets metric
            await collector.increment("cache.sets", 1)
            mock_counter.inc.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_prometheus_collector_gauge(self):
        """Test Prometheus gauge functionality."""
        from yokedcache.monitoring import PrometheusCollector

        with (
            patch("prometheus_client.Counter"),
            patch("prometheus_client.Gauge") as mock_gauge_class,
            patch("prometheus_client.Histogram"),
            patch("prometheus_client.Summary"),
            patch("prometheus_client.REGISTRY"),
        ):

            mock_gauge = Mock()
            mock_gauge.set = Mock()
            mock_gauge_class.return_value = mock_gauge

            collector = PrometheusCollector()
            collector._cache_size_gauge = mock_gauge

            await collector.gauge("cache.size_bytes", 1024)
            mock_gauge.set.assert_called_with(1024)

    @pytest.mark.asyncio
    async def test_prometheus_collector_histogram(self):
        """Test Prometheus histogram functionality."""
        from yokedcache.monitoring import PrometheusCollector

        with (
            patch("prometheus_client.Counter"),
            patch("prometheus_client.Gauge"),
            patch("prometheus_client.Histogram") as mock_histogram_class,
            patch("prometheus_client.Summary"),
            patch("prometheus_client.REGISTRY"),
        ):

            mock_histogram = Mock()
            mock_histogram.labels.return_value.observe = Mock()
            mock_histogram_class.return_value = mock_histogram

            collector = PrometheusCollector()
            collector._operation_duration = mock_histogram

            await collector.histogram(
                "cache.operation_duration", 0.5, {"operation": "get"}
            )
            mock_histogram.labels.assert_called_with(operation="get")
            mock_histogram.labels.return_value.observe.assert_called_with(0.5)


@pytest.mark.skipif(
    not pytest.importorskip("statsd", reason="statsd not available"),
    reason="StatsD client not available",
)
class TestStatsDCollector:
    """Test StatsD metrics collector."""

    def test_statsd_collector_initialization(self):
        """Test StatsDCollector initialization."""
        from yokedcache.monitoring import StatsDCollector

        with patch("statsd.StatsClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            collector = StatsDCollector(host="localhost", port=8125, prefix="test")
            assert collector.host == "localhost"
            assert collector.port == 8125
            assert collector.prefix == "test"
            assert collector.available is True
            assert collector.client == mock_client

    def test_statsd_collector_without_dependencies(self):
        """Test StatsDCollector when statsd is not available."""
        with patch.dict("sys.modules", {"statsd": None}):
            from yokedcache.monitoring import StatsDCollector

            collector = StatsDCollector()
            assert collector.available is False

    def test_statsd_metric_name_building(self):
        """Test building metric names with tags."""
        from yokedcache.monitoring import StatsDCollector

        with patch("statsd.StatsClient"):
            collector = StatsDCollector()

            # Test without tags
            name = collector._build_metric_name("test_metric")
            assert name == "test_metric"

            # Test with tags
            name = collector._build_metric_name(
                "test_metric", {"env": "prod", "service": "api"}
            )
            assert (
                "test_metric,env=prod,service=api" == name
                or "test_metric,service=api,env=prod" == name
            )

    @pytest.mark.asyncio
    async def test_statsd_collector_increment(self):
        """Test StatsD increment functionality."""
        from yokedcache.monitoring import StatsDCollector

        with patch("statsd.StatsClient") as mock_client_class:
            mock_client = Mock()
            mock_client.increment = Mock()
            mock_client_class.return_value = mock_client

            collector = StatsDCollector()

            await collector.increment("test_metric", 5, {"tag": "value"})
            mock_client.increment.assert_called_once()

    @pytest.mark.asyncio
    async def test_statsd_collector_gauge(self):
        """Test StatsD gauge functionality."""
        from yokedcache.monitoring import StatsDCollector

        with patch("statsd.StatsClient") as mock_client_class:
            mock_client = Mock()
            mock_client.gauge = Mock()
            mock_client_class.return_value = mock_client

            collector = StatsDCollector()

            await collector.gauge("test_metric", 100.0, {"tag": "value"})
            mock_client.gauge.assert_called_once()

    @pytest.mark.asyncio
    async def test_statsd_collector_histogram(self):
        """Test StatsD histogram functionality."""
        from yokedcache.monitoring import StatsDCollector

        with patch("statsd.StatsClient") as mock_client_class:
            mock_client = Mock()
            mock_client.histogram = Mock()
            mock_client_class.return_value = mock_client

            collector = StatsDCollector()

            await collector.histogram("test_metric", 0.5, {"tag": "value"})
            mock_client.histogram.assert_called_once()

    @pytest.mark.asyncio
    async def test_statsd_collector_timing(self):
        """Test StatsD timing functionality."""
        from yokedcache.monitoring import StatsDCollector

        with patch("statsd.StatsClient") as mock_client_class:
            mock_client = Mock()
            mock_client.timing = Mock()
            mock_client_class.return_value = mock_client

            collector = StatsDCollector()

            await collector.timing("test_metric", 1.5, {"tag": "value"})
            mock_client.timing.assert_called_once()

    @pytest.mark.asyncio
    async def test_statsd_collector_error_handling(self):
        """Test StatsD error handling."""
        from yokedcache.monitoring import StatsDCollector

        with patch("statsd.StatsClient") as mock_client_class:
            mock_client = Mock()
            mock_client.increment = Mock(side_effect=Exception("StatsD error"))
            mock_client_class.return_value = mock_client

            collector = StatsDCollector()

            # Should not raise exception
            await collector.increment("test_metric", 1)


class TestMonitoringIntegration:
    """Test integration of monitoring with cache operations."""

    @pytest.mark.asyncio
    async def test_multiple_collectors(self):
        """Test using multiple collectors simultaneously."""
        mock_collector1 = Mock()
        mock_collector1.increment = AsyncMock()
        mock_collector1.gauge = AsyncMock()

        mock_collector2 = Mock()
        mock_collector2.increment = AsyncMock()
        mock_collector2.gauge = AsyncMock()

        metrics = CacheMetrics([mock_collector1, mock_collector2])

        await metrics.increment("test_metric", 1)
        await metrics.gauge("test_gauge", 100.0)

        # Both collectors should be called
        mock_collector1.increment.assert_called_once()
        mock_collector1.gauge.assert_called_once()
        mock_collector2.increment.assert_called_once()
        mock_collector2.gauge.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_collector_failure(self):
        """Test behavior when one collector fails."""
        working_collector = Mock()
        working_collector.increment = AsyncMock()

        failing_collector = Mock()
        failing_collector.increment = AsyncMock(
            side_effect=Exception("Collector failed")
        )

        metrics = CacheMetrics([working_collector, failing_collector])

        # Should not raise exception even if one collector fails
        await metrics.increment("test_metric", 1)

        # Working collector should still be called
        working_collector.increment.assert_called_once()
        failing_collector.increment.assert_called_once()
