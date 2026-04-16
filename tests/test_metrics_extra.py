"""
Tests for uncovered paths in metrics.py.
"""

import asyncio

import pytest

from yokedcache.metrics import (
    CacheMetrics,
    OperationMetric,
    get_global_metrics,
    set_global_metrics,
)

# ---------------------------------------------------------------------------
# 1. CacheMetrics() thread lock initialization
# ---------------------------------------------------------------------------


def test_cache_metrics_lock_init():
    m = CacheMetrics()
    assert m._lock is not None
    assert m.max_operation_history == 1000


# ---------------------------------------------------------------------------
# 2. record_operation with table hit
# ---------------------------------------------------------------------------


def test_record_operation_table_hit():
    m = CacheMetrics()
    metric = OperationMetric(
        operation_type="get",
        key="test:key",
        duration_ms=1.5,
        success=True,
        cache_hit=True,
        table="users",
    )
    m.record_operation(metric)
    assert m.hit_counts["table:users"] == 1
    assert m.table_metrics["users"]["hits"] == 1


def test_record_operation_table_miss():
    m = CacheMetrics()
    metric = OperationMetric(
        operation_type="get",
        key="test:key",
        duration_ms=1.5,
        success=True,
        cache_hit=False,
        table="users",
    )
    m.record_operation(metric)
    assert m.miss_counts["table:users"] == 1
    assert m.table_metrics["users"]["misses"] == 1


# ---------------------------------------------------------------------------
# 3. record_operation with tags on hit
# ---------------------------------------------------------------------------


def test_record_operation_tag_hit():
    m = CacheMetrics()
    metric = OperationMetric(
        operation_type="get",
        key="test:key",
        duration_ms=2.0,
        success=True,
        cache_hit=True,
        tags={"user"},
    )
    m.record_operation(metric)
    assert m.hit_counts["tag:user"] == 1
    assert m.tag_metrics["user"]["hits"] == 1


def test_record_operation_tag_miss():
    m = CacheMetrics()
    metric = OperationMetric(
        operation_type="get",
        key="test:key",
        duration_ms=2.0,
        success=True,
        cache_hit=False,
        tags={"user"},
    )
    m.record_operation(metric)
    assert m.miss_counts["tag:user"] == 1
    assert m.tag_metrics["user"]["misses"] == 1


# ---------------------------------------------------------------------------
# 4. record_operation with table and operation_type="set" (and trimming >1000)
# ---------------------------------------------------------------------------


def test_record_operation_table_set():
    m = CacheMetrics()
    metric = OperationMetric(
        operation_type="set",
        key="test:key",
        duration_ms=0.5,
        success=True,
        table="users",
    )
    m.record_operation(metric)
    assert m.table_metrics["users"]["sets"] == 1


def test_record_operation_trimming():
    """Test that operation_times is trimmed when > 1000 entries."""
    m = CacheMetrics()
    # Add 1001 operations
    for i in range(1001):
        metric = OperationMetric(
            operation_type="get",
            key=f"key:{i}",
            duration_ms=float(i),
            success=True,
            cache_hit=True,
        )
        m.record_operation(metric)
    # Should be trimmed to 1000
    assert len(m.operation_times["get"]) <= 1000


# ---------------------------------------------------------------------------
# 5. record_operation with tags on failure (success=False)
# ---------------------------------------------------------------------------


def test_record_operation_tag_failure():
    m = CacheMetrics()
    metric = OperationMetric(
        operation_type="get",
        key="test:key",
        duration_ms=5.0,
        success=False,
        tags={"user"},
        error_type="ConnectionError",
    )
    m.record_operation(metric)
    assert m.tag_metrics["user"]["error_count"] == 1
    assert m.error_counts["ConnectionError"] >= 1


# ---------------------------------------------------------------------------
# 6. get_error_rate with specific operation_type
# ---------------------------------------------------------------------------


def test_get_error_rate_specific_operation():
    m = CacheMetrics()
    # Add one success and one failure for "get"
    m.record_operation(OperationMetric("get", "k", 1.0, True, cache_hit=True))
    m.record_operation(OperationMetric("get", "k", 1.0, False, error_type="Err"))

    rate = m.get_error_rate("get")
    assert 0 < rate <= 100

    # Without operation_type
    rate_all = m.get_error_rate()
    assert 0 <= rate_all <= 100


# ---------------------------------------------------------------------------
# 7. get_average_response_time with specific operation_type
# ---------------------------------------------------------------------------


def test_get_average_response_time_specific():
    m = CacheMetrics()
    m.record_operation(OperationMetric("get", "k", 2.0, True, cache_hit=True))
    m.record_operation(OperationMetric("get", "k", 4.0, True, cache_hit=True))
    avg = m.get_average_response_time("get")
    assert abs(avg - 3.0) < 0.1


# ---------------------------------------------------------------------------
# 8. get_percentile_response_time
# ---------------------------------------------------------------------------


def test_get_percentile_response_time():
    m = CacheMetrics()
    for i in range(100):
        m.record_operation(
            OperationMetric("get", f"k{i}", float(i), True, cache_hit=True)
        )
    p95 = m.get_percentile_response_time(95.0)
    assert p95 > 0


def test_get_percentile_response_time_with_operation():
    m = CacheMetrics()
    for i in range(10):
        m.record_operation(OperationMetric("set", f"k{i}", float(i), True))
    p50 = m.get_percentile_response_time(50.0, operation_type="set")
    assert p50 >= 0


def test_record_operation_table_error():
    """Test table error_count increment (line 177)."""
    m = CacheMetrics()
    metric = OperationMetric(
        operation_type="get",
        key="test:key",
        duration_ms=5.0,
        success=False,
        table="users",
        error_type="ConnectionError",
    )
    m.record_operation(metric)
    assert m.table_metrics["users"]["error_count"] == 1


def test_record_operation_table_avg_response_time():
    """Test avg_response_time for table (line 182)."""
    m = CacheMetrics()
    # Add some timing data for the table
    for i in range(3):
        metric = OperationMetric(
            operation_type="get",
            key=f"key:{i}",
            duration_ms=float(i + 1),
            success=True,
            cache_hit=True,
            table="orders",
        )
        m.record_operation(metric)
        # Also add to table-specific timing
        m.operation_times[f"table:orders"].append(float(i + 1))
    # Trigger the avg_response_time update
    metric = OperationMetric(
        operation_type="get",
        key="key:extra",
        duration_ms=4.0,
        success=True,
        cache_hit=True,
        table="orders",
    )
    m.record_operation(metric)
    assert m.table_metrics["orders"]["avg_response_time"] >= 0


# ---------------------------------------------------------------------------
# 9. reset_metrics
# ---------------------------------------------------------------------------


def test_reset_metrics():
    m = CacheMetrics()
    m.record_operation(OperationMetric("get", "k", 1.0, True, cache_hit=True))
    m.record_operation(OperationMetric("set", "k", 1.0, True))

    assert len(m.recent_operations) > 0
    m.reset_metrics()

    assert len(m.recent_operations) == 0
    assert len(m.operation_counts) == 0
    assert len(m.hit_counts) == 0
    assert m.last_reset_time is not None


# ---------------------------------------------------------------------------
# 10. start_background_collection and stop_background_collection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_stop_background_collection():
    m = CacheMetrics()
    assert m._metrics_task is None

    await m.start_background_collection(interval_seconds=100)
    assert m._metrics_task is not None

    # Starting again should be no-op
    task1 = m._metrics_task
    await m.start_background_collection(interval_seconds=100)
    assert m._metrics_task is task1  # same task

    await m.stop_background_collection()
    assert m._metrics_task is None


@pytest.mark.asyncio
async def test_stop_background_collection_not_started():
    m = CacheMetrics()
    # Should not raise even if not started
    await m.stop_background_collection()


# ---------------------------------------------------------------------------
# 11. get_global_metrics when _global_metrics is None
# ---------------------------------------------------------------------------


def test_get_global_metrics_creates_if_none():
    import yokedcache.metrics as metrics_mod

    original = metrics_mod._global_metrics
    metrics_mod._global_metrics = None

    result = get_global_metrics()
    assert result is not None
    assert isinstance(result, CacheMetrics)

    # Restore
    metrics_mod._global_metrics = original


# ---------------------------------------------------------------------------
# 12. set_global_metrics
# ---------------------------------------------------------------------------


def test_set_global_metrics():
    import yokedcache.metrics as metrics_mod

    original = metrics_mod._global_metrics

    new_metrics = CacheMetrics(max_operation_history=500)
    set_global_metrics(new_metrics)

    assert metrics_mod._global_metrics is new_metrics

    # Restore
    metrics_mod._global_metrics = original
