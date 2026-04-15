"""Tests for tracing.py covering uncovered branches."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache.tracing import (
    TRACING_AVAILABLE,
    CacheTracer,
    get_tracer,
    initialize_tracing,
    trace_cache_operation,
)


class TestCacheTracerDisabled:
    """Tests for CacheTracer when explicitly disabled."""

    def test_tracer_disabled_on_init(self):
        tracer = CacheTracer("test-svc", enabled=False)
        assert tracer.enabled is False
        assert tracer._tracer is None

    def test_tracer_disabled_skips_trace_hit(self):
        tracer = CacheTracer("test-svc", enabled=False)
        # Must not raise
        tracer.trace_hit("mykey")
        tracer.trace_hit("mykey", backend="memory")

    def test_tracer_disabled_skips_trace_miss(self):
        tracer = CacheTracer("test-svc", enabled=False)
        tracer.trace_miss("mykey")
        tracer.trace_miss("mykey", backend="redis")

    def test_tracer_disabled_skips_add_event(self):
        tracer = CacheTracer("test-svc", enabled=False)
        tracer.add_event("cache.op", key="k")

    @pytest.mark.asyncio
    async def test_trace_operation_disabled_yields_none(self):
        tracer = CacheTracer("test-svc", enabled=False)
        async with tracer.trace_operation("get", "k") as span:
            assert span is None


@pytest.mark.skipif(not TRACING_AVAILABLE, reason="OpenTelemetry not installed")
class TestCacheTracerEnabled:
    """Tests for CacheTracer when OTel is available."""

    def test_tracer_enabled_creates_otel_tracer(self):
        tracer = CacheTracer("my-service", enabled=True)
        assert tracer.enabled is True
        assert tracer._tracer is not None

    @pytest.mark.asyncio
    async def test_trace_operation_happy_path(self):
        tracer = CacheTracer("my-service", enabled=True)
        async with tracer.trace_operation(
            "get", key="testkey", backend="redis"
        ) as span:
            assert span is not None

    @pytest.mark.asyncio
    async def test_trace_operation_records_error(self):
        tracer = CacheTracer("my-service", enabled=True)
        with pytest.raises(ValueError):
            async with tracer.trace_operation("get", key="bad") as span:
                raise ValueError("test error")

    @pytest.mark.asyncio
    async def test_trace_operation_no_key(self):
        tracer = CacheTracer("my-service", enabled=True)
        async with tracer.trace_operation("flush") as span:
            assert span is not None

    def test_trace_hit_with_backend(self):
        tracer = CacheTracer("my-service", enabled=True)
        # Should not raise
        tracer.trace_hit("mykey", backend="redis")

    def test_trace_hit_without_backend(self):
        tracer = CacheTracer("my-service", enabled=True)
        tracer.trace_hit("mykey")

    def test_trace_miss_with_backend(self):
        tracer = CacheTracer("my-service", enabled=True)
        tracer.trace_miss("mykey", backend="memory")

    def test_trace_miss_without_backend(self):
        tracer = CacheTracer("my-service", enabled=True)
        tracer.trace_miss("mykey")

    def test_add_event_enabled(self):
        tracer = CacheTracer("my-service", enabled=True)
        # No active span, so get_current_span returns a no-op span
        tracer.add_event("cache.invalidate", tag="my-tag")


class TestInitializeTracing:
    """Tests for initialize_tracing global function."""

    def test_initialize_returns_tracer(self):
        tracer = initialize_tracing("test-app", enabled=True, sample_rate=1.0)
        assert tracer is not None
        assert tracer.service_name == "test-app"

    def test_initialize_sets_global_tracer(self):
        initialize_tracing("global-test", enabled=True)
        assert get_tracer() is not None

    def test_initialize_disabled(self):
        tracer = initialize_tracing("disabled-app", enabled=False)
        assert tracer.enabled is False

    @pytest.mark.skipif(not TRACING_AVAILABLE, reason="OpenTelemetry not installed")
    def test_initialize_with_sample_rate(self):
        """Test initialization with sample rate < 1.0 (triggers SDK sampling path)."""
        tracer = initialize_tracing("sampled-app", enabled=True, sample_rate=0.5)
        assert tracer is not None

    @patch("yokedcache.tracing.TRACING_AVAILABLE", False)
    def test_initialize_when_otel_unavailable(self):
        tracer = initialize_tracing("no-otel", enabled=True)
        assert tracer.enabled is False

    @patch("yokedcache.tracing.TRACING_AVAILABLE", False)
    def test_initialize_logs_warning_when_unavailable(self):
        with patch("yokedcache.tracing.logger") as mock_log:
            initialize_tracing("warn-svc", enabled=True)
            mock_log.warning.assert_called()


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_get_tracer_returns_last_initialized(self):
        t = initialize_tracing("get-tracer-test", enabled=True)
        result = get_tracer()
        assert result is t


class TestTraceCacheOperation:
    """Tests for trace_cache_operation convenience context manager."""

    @pytest.mark.asyncio
    async def test_trace_cache_operation_with_tracer(self):
        initialize_tracing("ctx-test", enabled=True)
        async with trace_cache_operation("get", "somekey") as span:
            # span may be None (no-op) or a real span
            pass

    @pytest.mark.asyncio
    async def test_trace_cache_operation_without_tracer(self):
        # Reset global tracer to None
        import yokedcache.tracing as tracing_mod

        original = tracing_mod._global_tracer
        tracing_mod._global_tracer = None
        try:
            async with trace_cache_operation("get", "key") as span:
                assert span is None
        finally:
            tracing_mod._global_tracer = original

    @pytest.mark.asyncio
    async def test_trace_cache_operation_no_key(self):
        initialize_tracing("no-key-test", enabled=True)
        async with trace_cache_operation("flush") as span:
            pass
