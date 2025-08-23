"""
Monitoring and metrics support for YokedCache.

This module provides integration with monitoring systems like Prometheus
and StatsD for real-time metrics collection in production environments.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class MetricsCollector(ABC):
    """Abstract base class for metrics collectors."""

    @abstractmethod
    async def increment(
        self, metric: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        pass

    @abstractmethod
    async def gauge(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric."""
        pass

    @abstractmethod
    async def histogram(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a histogram value."""
        pass

    @abstractmethod
    async def timing(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a timing metric."""
        pass


class PrometheusCollector(MetricsCollector):
    """Prometheus metrics collector."""

    def __init__(self, namespace: str = "yokedcache", registry=None):
        """Initialize Prometheus collector."""
        self.namespace = namespace

        try:
            from prometheus_client import (
                CollectorRegistry,
                Counter,
                Gauge,
                Histogram,
                Summary,
            )

            if registry is None:
                from prometheus_client import REGISTRY

                registry = REGISTRY

            self.registry = registry

            # Define metrics
            self.counters: Dict[str, Any] = {}
            self.gauges: Dict[str, Any] = {}
            self.histograms: Dict[str, Any] = {}
            self.summaries: Dict[str, Any] = {}

            # Cache operation counters
            self._get_counter = Counter(
                f"{namespace}_cache_gets_total",
                "Total cache get operations",
                ["result"],  # hit, miss
                registry=registry,
            )

            self._set_counter = Counter(
                f"{namespace}_cache_sets_total",
                "Total cache set operations",
                registry=registry,
            )

            self._delete_counter = Counter(
                f"{namespace}_cache_deletes_total",
                "Total cache delete operations",
                registry=registry,
            )

            self._invalidation_counter = Counter(
                f"{namespace}_cache_invalidations_total",
                "Total cache invalidations",
                ["type"],  # pattern, tags, manual
                registry=registry,
            )

            # Cache metrics gauges
            self._cache_size_gauge = Gauge(
                f"{namespace}_cache_size_bytes",
                "Current cache size in bytes",
                registry=registry,
            )

            self._cache_keys_gauge = Gauge(
                f"{namespace}_cache_keys_total",
                "Total number of cache keys",
                registry=registry,
            )

            self._hit_rate_gauge = Gauge(
                f"{namespace}_cache_hit_rate", "Cache hit rate (0-1)", registry=registry
            )

            # Operation timing
            self._operation_duration = Histogram(
                f"{namespace}_operation_duration_seconds",
                "Duration of cache operations",
                ["operation"],  # get, set, delete, etc.
                registry=registry,
            )

            self.available = True
            logger.info("Prometheus metrics collector initialized")

        except ImportError:
            logger.warning(
                "prometheus_client not available, Prometheus metrics disabled"
            )
            self.available = False

    async def increment(
        self, metric: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        if not self.available:
            return

        # Map common cache metrics to predefined counters
        if metric == "cache.gets":
            result = tags.get("result", "unknown") if tags else "unknown"
            self._get_counter.labels(result=result).inc(value)
        elif metric == "cache.sets":
            self._set_counter.inc(value)
        elif metric == "cache.deletes":
            self._delete_counter.inc(value)
        elif metric == "cache.invalidations":
            invalidation_type = tags.get("type", "manual") if tags else "manual"
            self._invalidation_counter.labels(type=invalidation_type).inc(value)

    async def gauge(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric."""
        if not self.available:
            return

        # Map common cache metrics to predefined gauges
        if metric == "cache.size_bytes":
            self._cache_size_gauge.set(value)
        elif metric == "cache.keys_total":
            self._cache_keys_gauge.set(value)
        elif metric == "cache.hit_rate":
            self._hit_rate_gauge.set(value)

    async def histogram(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a histogram value."""
        if not self.available:
            return

        # Map operation durations
        if metric == "cache.operation_duration":
            operation = tags.get("operation", "unknown") if tags else "unknown"
            self._operation_duration.labels(operation=operation).observe(value)

    async def timing(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a timing metric."""
        await self.histogram(metric, value, tags)


class StatsDCollector(MetricsCollector):
    """StatsD metrics collector."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "yokedcache",
        max_buffer_size: int = 50,
    ):
        """Initialize StatsD collector."""
        self.host = host
        self.port = port
        self.prefix = prefix
        self.max_buffer_size = max_buffer_size

        try:
            import statsd

            self.client = statsd.StatsClient(host=host, port=port, prefix=prefix)

            self.available = True
            logger.info(f"StatsD metrics collector initialized ({host}:{port})")

        except ImportError:
            logger.warning("statsd not available, StatsD metrics disabled")
            self.available = False

    def _build_metric_name(
        self, metric: str, tags: Optional[Dict[str, str]] = None
    ) -> str:
        """Build metric name with tags."""
        name = metric

        if tags:
            # Convert tags to StatsD format (some implementations support tags)
            tag_str = ",".join([f"{k}={v}" for k, v in tags.items()])
            name = f"{metric},{tag_str}"

        return name

    async def increment(
        self, metric: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        if not self.available:
            return

        try:
            metric_name = self._build_metric_name(metric, tags)
            self.client.increment(metric_name, value)
        except Exception as e:
            logger.debug(f"Error sending StatsD increment: {e}")

    async def gauge(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric."""
        if not self.available:
            return

        try:
            metric_name = self._build_metric_name(metric, tags)
            self.client.gauge(metric_name, value)
        except Exception as e:
            logger.debug(f"Error sending StatsD gauge: {e}")

    async def histogram(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a histogram value."""
        if not self.available:
            return

        try:
            metric_name = self._build_metric_name(metric, tags)
            self.client.histogram(metric_name, value)
        except Exception as e:
            logger.debug(f"Error sending StatsD histogram: {e}")

    async def timing(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a timing metric."""
        if not self.available:
            return

        try:
            metric_name = self._build_metric_name(metric, tags)
            self.client.timing(metric_name, value)
        except Exception as e:
            logger.debug(f"Error sending StatsD timing: {e}")


class NoOpCollector(MetricsCollector):
    """No-op metrics collector for when monitoring is disabled."""

    async def increment(
        self, metric: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """No-op increment."""
        pass

    async def gauge(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """No-op gauge."""
        pass

    async def histogram(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """No-op histogram."""
        pass

    async def timing(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """No-op timing."""
        pass


class CacheMetrics:
    """Cache metrics wrapper that handles multiple collectors."""

    def __init__(self, collectors: Optional[list] = None):
        """Initialize with list of collectors."""
        self.collectors = collectors or [NoOpCollector()]
        self._operation_start_times: Dict[str, float] = {}

    def add_collector(self, collector: MetricsCollector) -> None:
        """Add a metrics collector."""
        if isinstance(self.collectors[0], NoOpCollector):
            self.collectors = [collector]
        else:
            self.collectors.append(collector)

    async def increment(
        self, metric: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment metric across all collectors."""
        for collector in self.collectors:
            try:
                await collector.increment(metric, value, tags)
            except Exception as e:
                logger.debug(f"Error in metrics collector: {e}")

    async def gauge(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set gauge metric across all collectors."""
        for collector in self.collectors:
            try:
                await collector.gauge(metric, value, tags)
            except Exception as e:
                logger.debug(f"Error in metrics collector: {e}")

    async def histogram(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record histogram across all collectors."""
        for collector in self.collectors:
            try:
                await collector.histogram(metric, value, tags)
            except Exception as e:
                logger.debug(f"Error in metrics collector: {e}")

    async def timing(
        self,
        metric: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record timing across all collectors."""
        for collector in self.collectors:
            try:
                await collector.timing(metric, value, tags)
            except Exception as e:
                logger.debug(f"Error in metrics collector: {e}")

    def start_timer(self, operation: str) -> str:
        """Start timing an operation."""
        timer_id = f"{operation}_{time.time()}"
        self._operation_start_times[timer_id] = time.time()
        return timer_id

    async def end_timer(self, timer_id: str, operation: str) -> None:
        """End timing an operation and record the duration."""
        if timer_id in self._operation_start_times:
            duration = time.time() - self._operation_start_times[timer_id]
            await self.timing(
                "cache.operation_duration", duration, {"operation": operation}
            )
            del self._operation_start_times[timer_id]
