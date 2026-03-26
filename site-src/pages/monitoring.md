# Monitoring

YokedCache exposes health checks, in-process stats, and pluggable metrics collectors for Prometheus, StatsD, and OpenTelemetry.

---

## Health checks

```python
# Boolean—is the backend reachable?
is_healthy = await cache.health()

# Full diagnostics
info = await cache.detailed_health_check()
```

`detailed_health_check()` returns:

```python
{
    "status": "healthy",          # "healthy" or "unhealthy"
    "backend_type": "redis",
    "redis_connected": True,
    "connection_pool": {
        "available": 48,
        "in_use": 2,
        "max": 50,
    },
    "circuit_breaker": {
        "state": "closed",        # "closed", "open", or "half_open"
        "failure_count": 0,
    },
    "hit_rate": 0.87,
    "uptime_seconds": 7200,
}
```

### FastAPI health endpoint

```python
from fastapi.responses import JSONResponse

@app.get("/health")
async def health():
    info = await cache.detailed_health_check()
    status_code = 200 if info["status"] == "healthy" else 503
    return JSONResponse(info, status_code=status_code)
```

### CLI

```bash
yokedcache ping              # connection check
yokedcache stats             # snapshot of current stats
yokedcache stats --watch     # live refresh every 2s
```

---

## In-process stats

Without any extras:

```python
stats = await cache.get_stats()

print(f"Hit rate:      {stats.hit_rate:.1%}")
print(f"Miss rate:     {stats.miss_rate:.1%}")
print(f"Keys:          {stats.key_count}")
print(f"Memory:        {stats.memory_usage_mb:.1f} MB")
print(f"Total ops:     {stats.total_operations}")
print(f"Hits:          {stats.cache_hits}")
print(f"Misses:        {stats.cache_misses}")
print(f"Uptime:        {stats.uptime_seconds}s")
```

---

## Metrics (Prometheus + StatsD)

Requires `pip install "yokedcache[observability]"` or `pip install "yokedcache[monitoring]"`.

### Available metrics

| Metric | Type | Description |
|--------|------|-------------|
| `cache.gets.total` | Counter | Total GET operations |
| `cache.sets.total` | Counter | Total SET operations |
| `cache.deletes.total` | Counter | Total DELETE operations |
| `cache.hits.total` | Counter | Cache hits |
| `cache.misses.total` | Counter | Cache misses |
| `cache.hit_rate` | Gauge | Current hit rate (0–1) |
| `cache.size_bytes` | Gauge | Approximate memory usage |
| `cache.keys_count` | Gauge | Number of keys |
| `cache.operation_duration_seconds` | Histogram | Operation latency |
| `cache.invalidations.total` | Counter | Total invalidations |
| `cache.errors.total` | Counter | Total errors |
| `cache.circuit_breaker_state` | Gauge | 0=closed, 1=half-open, 2=open |

---

## Prometheus

```python
from yokedcache import YokedCache
from yokedcache.config import CacheConfig
from yokedcache.monitoring import CacheMetrics, PrometheusCollector

metrics = CacheMetrics([
    PrometheusCollector(
        namespace="myapp",   # metrics prefixed with "myapp_cache_"
        port=9100,           # metrics endpoint port
    )
])

cache = YokedCache(CacheConfig(redis_url="redis://..."), metrics=metrics)
```

Metrics endpoint: `http://localhost:9100/metrics`

Sample output:

```
# HELP myapp_cache_hits_total Total cache hits
# TYPE myapp_cache_hits_total counter
myapp_cache_hits_total 12470.0

# HELP myapp_cache_hit_rate Current cache hit rate
# TYPE myapp_cache_hit_rate gauge
myapp_cache_hit_rate 0.891

# HELP myapp_cache_operation_duration_seconds Cache operation duration
# TYPE myapp_cache_operation_duration_seconds histogram
myapp_cache_operation_duration_seconds_bucket{operation="get",le="0.001"} 10240.0
myapp_cache_operation_duration_seconds_bucket{operation="get",le="0.01"} 13890.0
myapp_cache_operation_duration_seconds_bucket{operation="get",le="+Inf"} 14000.0
```

### Custom labels

```python
PrometheusCollector(
    namespace="myapp",
    port=9100,
    labels={
        "environment": "production",
        "region": "us-east-1",
        "service": "user-api",
    },
)
```

### Prometheus scrape config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'yokedcache'
    static_configs:
      - targets: ['app:9100']
    scrape_interval: 15s
```

### Useful PromQL queries

```promql
# Hit rate over the last 5 minutes
rate(myapp_cache_hits_total[5m])
  /
rate(myapp_cache_gets_total[5m])

# 95th percentile GET latency
histogram_quantile(
  0.95,
  rate(myapp_cache_operation_duration_seconds_bucket{operation="get"}[5m])
)

# Error rate
rate(myapp_cache_errors_total[5m])

# Invalidations per second
rate(myapp_cache_invalidations_total[5m])
```

### Alerting rules

```yaml
# alerts.yml
groups:
  - name: yokedcache
    rules:
      - alert: CacheHitRateLow
        expr: |
          rate(myapp_cache_hits_total[5m])
          /
          rate(myapp_cache_gets_total[5m]) < 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate below 80% for 5 minutes"
          description: "Current rate: {{ $value | humanizePercentage }}"

      - alert: CacheLatencyHigh
        expr: |
          histogram_quantile(0.95,
            rate(myapp_cache_operation_duration_seconds_bucket{operation="get"}[5m])
          ) > 0.01
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Cache p95 GET latency above 10ms"

      - alert: CacheCircuitBreakerOpen
        expr: myapp_cache_circuit_breaker_state == 2
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Cache circuit breaker is open—backend may be down"

      - alert: CacheErrorRateHigh
        expr: rate(myapp_cache_errors_total[5m]) > 1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Cache error rate above 1/s"
```

---

## StatsD

```python
from yokedcache.monitoring import StatsDCollector

metrics = CacheMetrics([
    StatsDCollector(
        host="statsd.example.com",
        port=8125,
        prefix="myapp.cache",
        sample_rate=1.0,
    )
])
```

**DataDog / DogStatsD** with tags:

```python
StatsDCollector(
    host="localhost",
    port=8125,
    prefix="myapp.cache",
    use_tags=True,  # enables DogStatsD tag format
)
```

Metrics emitted in real-time:

```
myapp.cache.gets:1|c|#result:hit
myapp.cache.gets:1|c|#result:miss
myapp.cache.hit_rate:0.89|g
myapp.cache.operation_duration:0.002|h|#operation:get
```

---

## OpenTelemetry

```bash
pip install "yokedcache[tracing]"
```

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from yokedcache.monitoring import OpenTelemetryCollector

tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)

metrics = CacheMetrics([OpenTelemetryCollector(tracer_provider=tracer_provider)])
cache = YokedCache(CacheConfig(...), metrics=metrics)
```

Each cache operation becomes a span:

```
cache.get [2.1ms]
  ├── key: "user:42"
  ├── hit: true
  └── backend: redis
```

---

## Combining collectors

Run Prometheus and StatsD simultaneously:

```python
from yokedcache.monitoring import CacheMetrics, PrometheusCollector, StatsDCollector

metrics = CacheMetrics([
    PrometheusCollector(namespace="myapp", port=9100),
    StatsDCollector(host="statsd.example.com", port=8125, prefix="myapp.cache"),
])

cache = YokedCache(CacheConfig(...), metrics=metrics)
```

---

## Grafana dashboard

Key panels to include:

| Panel | Query |
|-------|-------|
| Hit rate (gauge) | `rate(cache_hits_total[5m]) / rate(cache_gets_total[5m])` |
| Operations/sec (graph) | `rate(cache_gets_total[1m])` + `rate(cache_sets_total[1m])` |
| p50 / p95 / p99 latency | `histogram_quantile(0.95, rate(cache_operation_duration_seconds_bucket[5m]))` |
| Key count | `cache_keys_count` |
| Memory usage | `cache_size_bytes / 1024 / 1024` |
| Error rate | `rate(cache_errors_total[5m])` |
| Circuit breaker state | `cache_circuit_breaker_state` |
| Invalidations/sec | `rate(cache_invalidations_total[5m])` |

---

## What to watch

| Signal | Healthy | Warning |
|--------|---------|---------|
| Hit rate | > 80% | < 60% |
| GET p95 latency | < 5ms | > 20ms |
| Error rate | 0 | > 0.1/s |
| Circuit breaker | closed | half-open / open |
| Key evictions | 0 | > 0/s (Redis out of memory) |
