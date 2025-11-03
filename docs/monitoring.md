# Production Monitoring & Health Checks

YokedCache v0.2.1 includes comprehensive monitoring, health checking, and metrics collection capabilities for production environments. Monitor cache performance, track detailed metrics, and set up alerts using industry-standard tools like Prometheus and StatsD.

## Table of Contents

- [Overview](#overview)
- [Health Checks](#health-checks)
- [Metrics Collection](#metrics-collection)
- [Metrics Collectors](#metrics-collectors)
- [Prometheus Integration](#prometheus-integration)
- [StatsD Integration](#statsd-integration)
- [Custom Metrics](#custom-metrics)
- [Dashboards and Alerting](#dashboards-and-alerting)
- [Performance Monitoring](#performance-monitoring)
- [Real-time Performance Tracking](#real-time-performance-tracking)
- [Alerting and Notifications](#alerting-and-notifications)

## Overview

The monitoring system provides real-time insights into your cache performance through multiple metrics collectors that can run simultaneously. Whether you're using Prometheus for metrics collection or StatsD for real-time monitoring, YokedCache adapts to your infrastructure.

### Key Features

- **Multiple Collectors**: Run Prometheus and StatsD simultaneously
- **Cache Metrics**: Hit rates, miss rates, operation latency, memory usage
- **System Metrics**: Connection health, error rates, throughput
- **Custom Metrics**: Add your own application-specific metrics
- **Zero Configuration**: Works out of the box with sensible defaults
- **Production Ready**: Designed for high-performance production environments

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `cache.gets.total` | Counter | Total number of GET operations |
| `cache.sets.total` | Counter | Total number of SET operations |
| `cache.deletes.total` | Counter | Total number of DELETE operations |
| `cache.hits.total` | Counter | Total number of cache hits |
| `cache.misses.total` | Counter | Total number of cache misses |
| `cache.hit_rate` | Gauge | Current cache hit rate (0-1) |
| `cache.size_bytes` | Gauge | Current memory usage in bytes |
| `cache.keys_count` | Gauge | Current number of cached keys |
| `cache.operation_duration` | Histogram | Operation latency distribution |
| `cache.invalidations.total` | Counter | Total number of invalidations |

## Health Checks

### Basic Health Check

```python
from yokedcache import YokedCache

cache = YokedCache()

# Simple health check
is_healthy = await cache.health()
print(f"Cache is healthy: {is_healthy}")
```

### Detailed Health Check *(v0.2.1+)*

Get comprehensive health information including connection status, pool statistics, and performance metrics:

```python
# Detailed health check with full diagnostics
health_info = await cache.detailed_health_check()

print(f"Status: {health_info['status']}")
print(f"Redis connected: {health_info['redis_connected']}")
print(f"Connection pool: {health_info['connection_pool']}")
print(f"Circuit breaker: {health_info['circuit_breaker']}")
print(f"Performance metrics: {health_info['performance_metrics']}")
```

## Metrics Collection

### Enabling Metrics

```python
from yokedcache import YokedCache, CacheConfig

config = CacheConfig(
    enable_metrics=True,
    metrics_retention_days=7
)

cache = YokedCache(config=config)
cache.start_metrics_collection()
```

### Accessing Metrics

```python
# Get current metrics snapshot
metrics = cache.get_comprehensive_metrics()

print(f"Hit rate: {metrics.hit_rate:.2%}")
print(f"Average response time: {metrics.avg_response_time:.3f}s")
print(f"Total operations: {metrics.total_operations}")
```

## Metrics Collectors

### Basic Setup

```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import RedisBackend
from yokedcache.monitoring import CacheMetrics, PrometheusCollector, StatsDCollector

# Setup backend
backend = RedisBackend(redis_url="redis://localhost:6379/0")

# Setup monitoring
metrics = CacheMetrics([
    PrometheusCollector(namespace="myapp", port=8000),
    StatsDCollector(host="localhost", port=8125, prefix="myapp.cache")
])

# Create cache with monitoring
config = CacheConfig(backend=backend, metrics=metrics)
cache = YokedCache(config)
```

### No-Op Collector (Default)

```python
from yokedcache.monitoring import CacheMetrics, NoOpCollector

# Default behavior - no metrics collection
metrics = CacheMetrics()  # Uses NoOpCollector by default

# Explicit no-op collector
metrics = CacheMetrics([NoOpCollector()])
```

The NoOpCollector allows you to disable metrics collection without changing your application code.

## Prometheus Integration

### Installation

```bash
# Install Prometheus dependencies
pip install yokedcache[monitoring]

# Or install manually
pip install prometheus_client
```

### Basic Configuration

```python
from yokedcache.monitoring import PrometheusCollector

# Basic Prometheus setup
prometheus_collector = PrometheusCollector(
    namespace="yokedcache",    # Metric prefix
    port=8000,                 # HTTP port for metrics endpoint
    registry=None              # Use default registry
)

# Custom configuration
prometheus_collector = PrometheusCollector(
    namespace="myapp_cache",
    port=9090,
    subsystem="backend",       # Additional prefix
    labels={"environment": "production", "service": "api"}
)
```

### Metrics Endpoint

The Prometheus collector automatically exposes metrics on the specified port:

```bash
# View metrics
curl http://localhost:8000/metrics

# Example output:
# HELP yokedcache_cache_gets_total Total number of cache GET operations
# TYPE yokedcache_cache_gets_total counter
yokedcache_cache_gets_total{result="hit"} 1247.0
yokedcache_cache_gets_total{result="miss"} 153.0

# HELP yokedcache_cache_hit_rate Current cache hit rate
# TYPE yokedcache_cache_hit_rate gauge
yokedcache_cache_hit_rate 0.89

# HELP yokedcache_cache_operation_duration_seconds Cache operation duration
# TYPE yokedcache_cache_operation_duration_seconds histogram
yokedcache_cache_operation_duration_seconds_bucket{operation="get",le="0.001"} 1024.0
yokedcache_cache_operation_duration_seconds_bucket{operation="get",le="0.01"} 1389.0
```

### Custom Labels and Registry

```python
from prometheus_client import CollectorRegistry
from yokedcache.monitoring import PrometheusCollector

# Custom registry for isolation
custom_registry = CollectorRegistry()

collector = PrometheusCollector(
    namespace="myapp",
    port=8001,
    registry=custom_registry,
    labels={
        "environment": "production",
        "region": "us-east-1",
        "service": "user-service"
    }
)
```

## StatsD Integration

### Installation

```bash
# Install StatsD dependencies
pip install yokedcache[monitoring]

# Or install manually
pip install statsd
```

### Basic Configuration

```python
from yokedcache.monitoring import StatsDCollector

# Basic StatsD setup
statsd_collector = StatsDCollector(
    host="localhost",
    port=8125,
    prefix="yokedcache"
)

# Advanced configuration
statsd_collector = StatsDCollector(
    host="statsd.example.com",
    port=8125,
    prefix="myapp.cache",
    sample_rate=1.0,           # Sample all metrics
    timeout=5.0                # Socket timeout
)
```

### DataDog Integration

```python
# DataDog StatsD configuration
statsd_collector = StatsDCollector(
    host="localhost",
    port=8125,
    prefix="myapp.cache",
    use_tags=True              # Enable DataDog-style tags
)
```

### Metric Examples

StatsD metrics are sent in real-time:

```bash
# Counter metrics
myapp.cache.gets:1|c|#result:hit
myapp.cache.gets:1|c|#result:miss
myapp.cache.sets:1|c

# Gauge metrics
myapp.cache.hit_rate:0.89|g
myapp.cache.size_bytes:1048576|g
myapp.cache.keys_count:1500|g

# Histogram metrics
myapp.cache.operation_duration:0.002|h|#operation:get
myapp.cache.operation_duration:0.005|h|#operation:set
```

## Custom Metrics

### Adding Custom Collectors

```python
from yokedcache.monitoring import CacheMetrics
import asyncio

class CustomMetricsCollector:
    """Custom metrics collector example."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def increment(self, metric: str, value: float = 1, tags: dict = None):
        """Send increment to webhook."""
        data = {
            "type": "increment",
            "metric": metric,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time()
        }
        # Send to webhook (implementation depends on your system)
        await self._send_webhook(data)

    async def gauge(self, metric: str, value: float, tags: dict = None):
        """Send gauge to webhook."""
        data = {
            "type": "gauge",
            "metric": metric,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time()
        }
        await self._send_webhook(data)

    async def histogram(self, metric: str, value: float, tags: dict = None):
        """Send histogram to webhook."""
        # Implementation for histogram metrics
        pass

    async def timing(self, metric: str, value: float, tags: dict = None):
        """Send timing to webhook."""
        # Implementation for timing metrics
        pass

    async def _send_webhook(self, data: dict):
        """Send data to webhook endpoint."""
        # Implement webhook sending logic
        pass

# Use custom collector
custom_collector = CustomMetricsCollector("https://metrics.example.com/webhook")
metrics = CacheMetrics([custom_collector])
```

### Application-Specific Metrics

```python
async def track_business_metrics(cache_metrics: CacheMetrics):
    """Track business-specific metrics."""

    # Track user actions
    await cache_metrics.increment(
        "user.login",
        tags={"source": "api", "method": "oauth"}
    )

    # Track application state
    await cache_metrics.gauge(
        "active_sessions",
        value=get_active_session_count(),
        tags={"server": "web-01"}
    )

    # Track request processing time
    timer_id = cache_metrics.start_timer("request_processing")

    # ... process request ...

    await cache_metrics.end_timer(timer_id, "request_processing", {
        "endpoint": "/api/users",
        "status_code": "200"
    })
```

## Dashboards and Alerting

### Prometheus + Grafana Dashboard

```json
{
  "dashboard": {
    "title": "YokedCache Monitoring",
    "panels": [
      {
        "title": "Cache Hit Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "yokedcache_cache_hit_rate",
            "format": "time_series"
          }
        ]
      },
      {
        "title": "Operations per Second",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(yokedcache_cache_gets_total[5m])",
            "legendFormat": "Gets/sec"
          },
          {
            "expr": "rate(yokedcache_cache_sets_total[5m])",
            "legendFormat": "Sets/sec"
          }
        ]
      },
      {
        "title": "Operation Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(yokedcache_cache_operation_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(yokedcache_cache_operation_duration_seconds_bucket[5m]))",
            "legendFormat": "Median"
          }
        ]
      }
    ]
  }
}
```

### Prometheus Alerting Rules

```yaml
# prometheus-alerts.yml
groups:
- name: yokedcache
  rules:
  - alert: CacheHitRateLow
    expr: yokedcache_cache_hit_rate < 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Cache hit rate is below 80%"
      description: "Cache hit rate is {{ $value | humanizePercentage }}"

  - alert: CacheOperationLatencyHigh
    expr: histogram_quantile(0.95, rate(yokedcache_cache_operation_duration_seconds_bucket[5m])) > 0.1
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Cache operation latency is high"
      description: "95th percentile latency is {{ $value }}s"

  - alert: CacheMemoryUsageHigh
    expr: yokedcache_cache_size_bytes > 1000000000  # 1GB
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Cache memory usage is high"
      description: "Cache is using {{ $value | humanizeBytes }} of memory"
```

### DataDog Dashboard

```python
# datadog_dashboard.py
from datadog import initialize, api

# Setup DataDog
initialize(api_key='your-api-key', app_key='your-app-key')

# Create dashboard
dashboard = {
    'title': 'YokedCache Monitoring',
    'description': 'Monitor YokedCache performance and health',
    'widgets': [
        {
            'definition': {
                'type': 'timeseries',
                'title': 'Cache Hit Rate',
                'requests': [
                    {
                        'q': 'avg:myapp.cache.hit_rate{*}',
                        'display_type': 'line'
                    }
                ]
            }
        },
        {
            'definition': {
                'type': 'timeseries',
                'title': 'Cache Operations',
                'requests': [
                    {
                        'q': 'sum:myapp.cache.gets{*}.as_rate()',
                        'display_type': 'line'
                    },
                    {
                        'q': 'sum:myapp.cache.sets{*}.as_rate()',
                        'display_type': 'line'
                    }
                ]
            }
        }
    ]
}

api.Dashboard.create(dashboard=dashboard)
```

## Performance Monitoring

### Health Monitoring

```python
import asyncio
import time
from yokedcache.monitoring import CacheMetrics

class CacheHealthMonitor:
    """Monitor cache health and performance."""

    def __init__(self, cache: YokedCache, metrics: CacheMetrics):
        self.cache = cache
        self.metrics = metrics
        self.monitoring = True

    async def start_monitoring(self, interval: int = 60):
        """Start health monitoring loop."""
        while self.monitoring:
            await self._collect_health_metrics()
            await asyncio.sleep(interval)

    async def _collect_health_metrics(self):
        """Collect and report health metrics."""
        try:
            # Check backend health
            start_time = time.time()
            is_healthy = await self.cache.health_check()
            response_time = time.time() - start_time

            # Report health metrics
            await self.metrics.gauge("cache.health", 1.0 if is_healthy else 0.0)
            await self.metrics.timing("cache.health_check_duration", response_time)

            if is_healthy:
                # Collect performance metrics
                stats = await self.cache.get_stats()

                await self.metrics.gauge("cache.hit_rate", stats.hit_rate)
                await self.metrics.gauge("cache.size_bytes", stats.total_memory_bytes)
                await self.metrics.gauge("cache.keys_count", stats.total_keys)
                await self.metrics.gauge("cache.uptime_seconds", stats.uptime_seconds)

        except Exception as e:
            await self.metrics.increment("cache.health_check_errors")
            print(f"Health check failed: {e}")

    def stop_monitoring(self):
        """Stop health monitoring."""
        self.monitoring = False

# Usage
monitor = CacheHealthMonitor(cache, metrics)
asyncio.create_task(monitor.start_monitoring(interval=30))
```

### Performance Benchmarking

```python
import asyncio
import statistics
import time

async def benchmark_cache_performance(cache: YokedCache, metrics: CacheMetrics):
    """Benchmark cache performance and report metrics."""

    # Warm up cache
    print("Warming up cache...")
    for i in range(1000):
        await cache.set(f"benchmark:warm:{i}", f"value_{i}")

    # Benchmark GET operations
    print("Benchmarking GET operations...")
    get_times = []

    for i in range(1000):
        start = time.time()
        await cache.get(f"benchmark:warm:{i % 1000}")
        get_times.append(time.time() - start)

    # Report GET performance
    await metrics.gauge("benchmark.get.avg_latency", statistics.mean(get_times))
    await metrics.gauge("benchmark.get.p95_latency", statistics.quantiles(get_times, n=20)[18])
    await metrics.gauge("benchmark.get.p99_latency", statistics.quantiles(get_times, n=100)[98])

    # Benchmark SET operations
    print("Benchmarking SET operations...")
    set_times = []

    for i in range(1000):
        start = time.time()
        await cache.set(f"benchmark:set:{i}", f"benchmark_value_{i}")
        set_times.append(time.time() - start)

    # Report SET performance
    await metrics.gauge("benchmark.set.avg_latency", statistics.mean(set_times))
    await metrics.gauge("benchmark.set.p95_latency", statistics.quantiles(set_times, n=20)[18])
    await metrics.gauge("benchmark.set.p99_latency", statistics.quantiles(set_times, n=100)[98])

    # Calculate throughput
    total_ops = len(get_times) + len(set_times)
    total_time = max(get_times) + max(set_times)
    throughput = total_ops / total_time

    await metrics.gauge("benchmark.throughput_ops_per_sec", throughput)

    print(f"Benchmark complete:")
    print(f"  GET avg: {statistics.mean(get_times)*1000:.2f}ms")
    print(f"  SET avg: {statistics.mean(set_times)*1000:.2f}ms")
    print(f"  Throughput: {throughput:.0f} ops/sec")
```

### Error Rate Monitoring

```python
class ErrorTrackingMetrics:
    """Track and report error rates."""

    def __init__(self, metrics: CacheMetrics):
        self.metrics = metrics
        self.error_counts = {}

    async def track_error(self, operation: str, error_type: str, error: Exception):
        """Track an error occurrence."""
        error_key = f"{operation}.{error_type}"

        await self.metrics.increment("cache.errors.total", tags={
            "operation": operation,
            "error_type": error_type,
            "error_class": error.__class__.__name__
        })

        # Track error rate
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

    async def calculate_error_rates(self, total_operations: dict):
        """Calculate and report error rates."""
        for error_key, error_count in self.error_counts.items():
            operation = error_key.split('.')[0]
            total_ops = total_operations.get(operation, 1)
            error_rate = error_count / total_ops

            await self.metrics.gauge(f"cache.error_rate.{operation}", error_rate)

# Usage with cache operations
error_tracker = ErrorTrackingMetrics(metrics)

async def safe_cache_get(key: str):
    """Cache GET with error tracking."""
    try:
        return await cache.get(key)
    except ConnectionError as e:
        await error_tracker.track_error("get", "connection", e)
        return None
    except Exception as e:
        await error_tracker.track_error("get", "unknown", e)
        return None
```

## Real-time Performance Tracking

Monitor performance in real-time and alert on issues:

```python
# Monitor performance in real-time
async def monitor_cache_performance():
    while True:
        metrics = cache.get_comprehensive_metrics()

        # Alert on poor performance
        if metrics.hit_rate < 0.70:
            await send_alert(f"Low hit rate: {metrics.hit_rate:.2%}")

        if metrics.avg_response_time > 0.100:
            await send_alert(f"High latency: {metrics.avg_response_time:.3f}s")

        if metrics.error_rate > 0.01:
            await send_alert(f"High error rate: {metrics.error_rate:.3%}")

        await asyncio.sleep(30)  # Check every 30 seconds
```

## Alerting and Notifications

### Configuring Alerts

Set up automated alerting based on metrics thresholds:

```python
from yokedcache.monitoring import AlertManager

alert_manager = AlertManager(cache)

# Configure alert thresholds
alert_manager.add_alert(
    name="low_hit_rate",
    metric="hit_rate",
    threshold=0.70,
    comparison="less_than",
    webhook_url="https://your-webhook.com/alerts"
)

alert_manager.add_alert(
    name="high_latency",
    metric="avg_response_time",
    threshold=0.100,
    comparison="greater_than",
    email_recipients=["admin@yourcompany.com"]
)

# Start monitoring
alert_manager.start()
```

### Common Alert Patterns

**Performance Alerts:**
- Hit rate below 70%
- Average response time above 100ms
- Error rate above 1%

**Availability Alerts:**
- Redis connection failures
- Circuit breaker opened
- Connection pool exhaustion

**Capacity Alerts:**
- Memory usage above 80%
- Connection pool utilization above 90%
- Cache eviction rate above threshold

---

Production monitoring with YokedCache provides comprehensive visibility and insights needed to maintain high-performance caching systems. Use these tools to optimize performance, detect issues early, and ensure reliable operation in production environments.
