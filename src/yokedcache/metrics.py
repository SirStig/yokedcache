"""
Enhanced metrics collection for YokedCache.

This module provides comprehensive metrics collection, including operation timing,
error tracking, and performance monitoring suitable for production environments.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class OperationMetric:
    """Single operation metric record."""

    operation_type: str  # get, set, delete, etc.
    key: str
    duration_ms: float
    success: bool
    error_type: Optional[str] = None
    cache_hit: Optional[bool] = None  # Only for get operations
    table: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TimeSeries:
    """Time series data for metrics."""

    max_points: int = 1000
    data: deque = field(default_factory=deque)

    def add_point(self, value: float, timestamp: Optional[datetime] = None) -> None:
        """Add a data point to the time series."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        self.data.append((timestamp, value))

        # Keep only the most recent points
        if len(self.data) > self.max_points:
            self.data.popleft()

    def get_recent(self, minutes: int = 5) -> List[tuple]:
        """Get data points from the last N minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [(ts, val) for ts, val in self.data if ts >= cutoff]

    def get_average(self, minutes: int = 5) -> float:
        """Get average value over the last N minutes."""
        recent = self.get_recent(minutes)
        if not recent:
            return 0.0
        return sum(val for _, val in recent) / len(recent)


class CacheMetrics:
    """
    Comprehensive metrics collection for YokedCache.

    Tracks operation performance, error rates, hit rates, and system health.
    """

    def __init__(self, max_operation_history: int = 1000):
        """Initialize metrics collector."""
        self.max_operation_history = max_operation_history
        self._lock = Lock()

        # Operation counters
        self.operation_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)

        # Hit/miss tracking
        self.hit_counts: Dict[str, int] = defaultdict(int)
        self.miss_counts: Dict[str, int] = defaultdict(int)

        # Performance tracking
        self.operation_times: Dict[str, List[float]] = defaultdict(list)
        self.response_times = TimeSeries()
        self.hit_rate_series = TimeSeries()
        self.error_rate_series = TimeSeries()

        # Recent operations history
        self.recent_operations: deque = deque(maxlen=max_operation_history)

        # Table and tag specific metrics
        self.table_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_response_time": 0.0,
                "error_count": 0,
            }
        )

        self.tag_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_response_time": 0.0,
                "error_count": 0,
            }
        )

        # System metrics
        self.start_time = datetime.now(timezone.utc)
        self.last_reset_time = datetime.now(timezone.utc)

        # Background metrics collection
        self._metrics_task: Optional[asyncio.Task] = None
        self._should_stop = False

    def record_operation(self, metric: OperationMetric) -> None:
        """Record a cache operation metric."""
        with self._lock:
            # Update operation counts
            self.operation_counts[metric.operation_type] += 1

            if metric.success:
                self.success_counts[metric.operation_type] += 1
            else:
                self.error_counts[metric.operation_type] += 1
                if metric.error_type:
                    self.error_counts[metric.error_type] += 1

            # Track hit/miss for get operations
            if metric.operation_type == "get" and metric.cache_hit is not None:
                if metric.cache_hit:
                    self.hit_counts["total"] += 1
                    if metric.table:
                        self.hit_counts[f"table:{metric.table}"] += 1
                    for tag in metric.tags:
                        self.hit_counts[f"tag:{tag}"] += 1
                else:
                    self.miss_counts["total"] += 1
                    if metric.table:
                        self.miss_counts[f"table:{metric.table}"] += 1
                    for tag in metric.tags:
                        self.miss_counts[f"tag:{tag}"] += 1

            # Track response times
            self.operation_times[metric.operation_type].append(metric.duration_ms)
            self.response_times.add_point(metric.duration_ms)

            # Keep only recent timing data
            max_times = 1000
            if len(self.operation_times[metric.operation_type]) > max_times:
                self.operation_times[metric.operation_type] = self.operation_times[
                    metric.operation_type
                ][-max_times:]

            # Update table metrics
            if metric.table:
                table_stats = self.table_metrics[metric.table]
                if metric.operation_type == "get" and metric.cache_hit is not None:
                    if metric.cache_hit:
                        table_stats["hits"] += 1
                    else:
                        table_stats["misses"] += 1
                elif metric.operation_type in ["set", "delete"]:
                    table_stats[f"{metric.operation_type}s"] += 1

                if not metric.success:
                    table_stats["error_count"] += 1

                # Update average response time
                times = self.operation_times.get(f"table:{metric.table}", [])
                if times:
                    table_stats["avg_response_time"] = sum(times) / len(times)

            # Update tag metrics
            for tag in metric.tags:
                tag_stats = self.tag_metrics[tag]
                if metric.operation_type == "get" and metric.cache_hit is not None:
                    if metric.cache_hit:
                        tag_stats["hits"] += 1
                    else:
                        tag_stats["misses"] += 1
                elif metric.operation_type in ["set", "delete"]:
                    tag_stats[f"{metric.operation_type}s"] += 1

                if not metric.success:
                    tag_stats["error_count"] += 1

            # Add to recent operations
            self.recent_operations.append(metric)

    def get_hit_rate(self, key: str = "total") -> float:
        """Get hit rate for total or specific table/tag."""
        hits = self.hit_counts[key]
        misses = self.miss_counts[key]
        total = hits + misses

        if total == 0:
            return 0.0

        return (hits / total) * 100.0

    def get_error_rate(self, operation_type: Optional[str] = None) -> float:
        """Get error rate for specific operation or overall."""
        if operation_type:
            total_ops = self.operation_counts[operation_type]
            errors = self.error_counts[operation_type]
        else:
            total_ops = sum(self.operation_counts.values())
            errors = sum(self.error_counts.values())

        if total_ops == 0:
            return 0.0

        return (errors / total_ops) * 100.0

    def get_average_response_time(self, operation_type: Optional[str] = None) -> float:
        """Get average response time for specific operation or overall."""
        if operation_type:
            times = self.operation_times.get(operation_type, [])
        else:
            times = []
            for op_times in self.operation_times.values():
                times.extend(op_times)

        if not times:
            return 0.0

        return sum(times) / len(times)

    def get_percentile_response_time(
        self, percentile: float, operation_type: Optional[str] = None
    ) -> float:
        """Get percentile response time (e.g., 95th percentile)."""
        if operation_type:
            times = self.operation_times.get(operation_type, [])
        else:
            times = []
            for op_times in self.operation_times.values():
                times.extend(op_times)

        if not times:
            return 0.0

        sorted_times = sorted(times)
        index = int(len(sorted_times) * (percentile / 100.0))
        index = min(index, len(sorted_times) - 1)

        return sorted_times[index]

    def get_operations_per_second(self, minutes: int = 5) -> float:
        """Get operations per second over the last N minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        recent_ops = [op for op in self.recent_operations if op.timestamp >= cutoff]

        if not recent_ops:
            return 0.0

        time_span = minutes * 60  # Convert to seconds
        return len(recent_ops) / time_span

    def get_top_slow_operations(self, limit: int = 10) -> List[OperationMetric]:
        """Get the slowest operations from recent history."""
        slow_ops = sorted(
            self.recent_operations, key=lambda op: op.duration_ms, reverse=True
        )

        return list(slow_ops[:limit])

    def get_recent_errors(self, limit: int = 10) -> List[OperationMetric]:
        """Get recent failed operations."""
        errors = [op for op in self.recent_operations if not op.success]

        # Sort by most recent first
        errors.sort(key=lambda op: op.timestamp, reverse=True)

        return errors[:limit]

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        now = datetime.now(timezone.utc)
        uptime = now - self.start_time

        # Calculate overall stats
        total_operations = sum(self.operation_counts.values())
        total_errors = sum(self.error_counts.values())
        total_hits = self.hit_counts["total"]
        total_misses = self.miss_counts["total"]

        stats = {
            "timestamp": now.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "operations": {
                "total": total_operations,
                "by_type": dict(self.operation_counts),
                "per_second": self.get_operations_per_second(),
                "errors": {
                    "total": total_errors,
                    "rate_percent": self.get_error_rate(),
                    "by_type": dict(self.error_counts),
                },
            },
            "cache_performance": {
                "hit_rate_percent": self.get_hit_rate(),
                "total_hits": total_hits,
                "total_misses": total_misses,
            },
            "response_times": {
                "average_ms": self.get_average_response_time(),
                "p50_ms": self.get_percentile_response_time(50),
                "p95_ms": self.get_percentile_response_time(95),
                "p99_ms": self.get_percentile_response_time(99),
                "recent_5min_avg_ms": self.response_times.get_average(5),
            },
            "tables": {
                table: {
                    **stats,
                    "hit_rate_percent": self.get_hit_rate(f"table:{table}"),
                }
                for table, stats in self.table_metrics.items()
            },
            "tags": {
                tag: {
                    **stats,
                    "hit_rate_percent": self.get_hit_rate(f"tag:{tag}"),
                }
                for tag, stats in self.tag_metrics.items()
            },
            "slow_operations": [
                {
                    "operation": op.operation_type,
                    "key": op.key,
                    "duration_ms": op.duration_ms,
                    "timestamp": op.timestamp.isoformat(),
                    "table": op.table,
                    "tags": list(op.tags),
                }
                for op in self.get_top_slow_operations(5)
            ],
            "recent_errors": [
                {
                    "operation": op.operation_type,
                    "key": op.key,
                    "error_type": op.error_type,
                    "duration_ms": op.duration_ms,
                    "timestamp": op.timestamp.isoformat(),
                    "table": op.table,
                    "tags": list(op.tags),
                }
                for op in self.get_recent_errors(5)
            ],
        }

        return stats

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self.operation_counts.clear()
            self.error_counts.clear()
            self.success_counts.clear()
            self.hit_counts.clear()
            self.miss_counts.clear()
            self.operation_times.clear()
            self.recent_operations.clear()
            self.table_metrics.clear()
            self.tag_metrics.clear()

            # Reset time series
            self.response_times = TimeSeries()
            self.hit_rate_series = TimeSeries()
            self.error_rate_series = TimeSeries()

            self.last_reset_time = datetime.now(timezone.utc)
            logger.info("Cache metrics reset")

    async def start_background_collection(self, interval_seconds: int = 60) -> None:
        """Start background metrics collection task."""
        if self._metrics_task is not None:
            return  # Already running

        async def _collect_metrics():
            while not self._should_stop:
                try:
                    # Update time series with current metrics
                    hit_rate = self.get_hit_rate()
                    error_rate = self.get_error_rate()
                    avg_response_time = self.get_average_response_time()

                    self.hit_rate_series.add_point(hit_rate)
                    self.error_rate_series.add_point(error_rate)
                    self.response_times.add_point(avg_response_time)

                    await asyncio.sleep(interval_seconds)

                except Exception as e:
                    logger.error(f"Error in background metrics collection: {e}")
                    await asyncio.sleep(interval_seconds)

        self._metrics_task = asyncio.create_task(_collect_metrics())
        logger.info(
            f"Started background metrics collection (interval: {interval_seconds}s)"
        )

    async def stop_background_collection(self) -> None:
        """Stop background metrics collection task."""
        self._should_stop = True

        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass

            self._metrics_task = None

        logger.info("Stopped background metrics collection")


# Global metrics instance for convenience
_global_metrics: Optional[CacheMetrics] = None


def get_global_metrics() -> CacheMetrics:
    """Get the global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = CacheMetrics()
    return _global_metrics


def set_global_metrics(metrics: CacheMetrics) -> None:
    """Set the global metrics instance."""
    global _global_metrics
    _global_metrics = metrics
