"""OpenTelemetry tracing integration for YokedCache.

Provides optional distributed tracing capabilities for cache operations
using OpenTelemetry spans and metrics.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

logger = logging.getLogger(__name__)

# Optional OpenTelemetry imports
try:
    from opentelemetry import trace
    from opentelemetry.semconv.trace import SpanAttributes
    from opentelemetry.trace import Status, StatusCode

    TRACING_AVAILABLE = True
except ImportError:
    trace = None
    Status = None
    StatusCode = None
    SpanAttributes = None
    TRACING_AVAILABLE = False


class CacheTracer:
    """Manages OpenTelemetry tracing for cache operations."""

    def __init__(self, service_name: str = "yokedcache", enabled: bool = True):
        """Initialize the cache tracer."""
        self.service_name = service_name
        self.enabled = enabled and TRACING_AVAILABLE
        self._tracer = None

        if self.enabled:
            self._tracer = trace.get_tracer(service_name)
            logger.debug(f"Initialized OpenTelemetry tracer for {service_name}")
        elif enabled and not TRACING_AVAILABLE:
            logger.warning("OpenTelemetry not available, tracing disabled")

    @asynccontextmanager
    async def trace_operation(
        self, operation: str, key: Optional[str] = None, **attributes: Any
    ) -> AsyncGenerator[Optional[Any], None]:
        """Trace a cache operation with automatic span management."""
        if not self.enabled or not self._tracer:
            yield None
            return

        span_name = f"cache.{operation}"

        with self._tracer.start_as_current_span(span_name) as span:
            try:
                # Set standard attributes
                span.set_attribute("cache.operation", operation)
                if key:
                    span.set_attribute("cache.key", key)
                span.set_attribute("cache.service", self.service_name)

                # Set custom attributes
                for attr_key, attr_value in attributes.items():
                    if attr_value is not None:
                        span.set_attribute(f"cache.{attr_key}", str(attr_value))

                yield span

                # Mark as successful if no exception
                span.set_status(Status(StatusCode.OK))

            except Exception as e:
                # Record error information
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("cache.error", True)
                span.set_attribute("cache.error.type", type(e).__name__)
                span.set_attribute("cache.error.message", str(e))
                raise

    def trace_hit(self, key: str, backend: Optional[str] = None) -> None:
        """Record a cache hit event."""
        if not self.enabled or not self._tracer:
            return

        with self._tracer.start_as_current_span("cache.hit") as span:
            span.set_attribute("cache.operation", "hit")
            span.set_attribute("cache.key", key)
            span.set_attribute("cache.result", "hit")
            if backend:
                span.set_attribute("cache.backend", backend)

    def trace_miss(self, key: str, backend: Optional[str] = None) -> None:
        """Record a cache miss event."""
        if not self.enabled or not self._tracer:
            return

        with self._tracer.start_as_current_span("cache.miss") as span:
            span.set_attribute("cache.operation", "miss")
            span.set_attribute("cache.key", key)
            span.set_attribute("cache.result", "miss")
            if backend:
                span.set_attribute("cache.backend", backend)

    def add_event(self, name: str, **attributes: Any) -> None:
        """Add an event to the current span if active."""
        if not self.enabled:
            return

        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event(name, attributes)


# Global tracer instance
_global_tracer: Optional[CacheTracer] = None


def initialize_tracing(
    service_name: str = "yokedcache", enabled: bool = True, sample_rate: float = 1.0
) -> CacheTracer:
    """Initialize global tracing configuration."""
    global _global_tracer

    if not TRACING_AVAILABLE and enabled:
        logger.warning(
            "OpenTelemetry not available. Install with: "
            "pip install opentelemetry-api opentelemetry-sdk"
        )
        enabled = False

    _global_tracer = CacheTracer(service_name, enabled)

    # Configure sampling if tracing is available
    if enabled and TRACING_AVAILABLE and sample_rate < 1.0:
        try:
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBasedSampler

            sampler = TraceIdRatioBasedSampler(sample_rate)
            trace.set_tracer_provider(TracerProvider(sampler=sampler))
            logger.debug(f"Set trace sampling rate to {sample_rate}")
        except ImportError:
            logger.warning("OpenTelemetry SDK not available for sampling configuration")

    return _global_tracer


def get_tracer() -> Optional[CacheTracer]:
    """Get the global tracer instance."""
    return _global_tracer


@asynccontextmanager
async def trace_cache_operation(
    operation: str, key: Optional[str] = None, **attributes: Any
) -> AsyncGenerator[Optional[Any], None]:
    """Convenience function for tracing cache operations."""
    tracer = get_tracer()
    if tracer:
        async with tracer.trace_operation(operation, key, **attributes) as span:
            yield span
    else:
        yield None
