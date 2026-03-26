# Configuration

Three ways to configure YokedCache: programmatic, YAML, or environment variables. They compose together—explicit arguments beat `CacheConfig`, which beats YAML, which beats env vars, which beats defaults.

---

## Programmatic

```python
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

config = CacheConfig(
    redis_url="redis://localhost:6379/0",
    default_ttl=300,
    key_prefix="myapp",
)
cache = YokedCache(config)
```

## From environment variables

```python
cache = YokedCache.from_env()
```

Reads all `YOKEDCACHE_*` env vars automatically.

## From YAML

```python
cache = YokedCache.from_yaml("cache.yaml")
```

```yaml
# cache.yaml
redis_url: redis://localhost:6379/0
default_ttl: 300
key_prefix: myapp
enable_fuzzy: true
log_level: INFO

tables:
  users:
    ttl: 3600
    tags: ["user_data"]
  products:
    ttl: 1800
    serialization_method: MSGPACK
```

---

## Full reference

### Connection

| Field | Type | Default | Env var | Notes |
|-------|------|---------|---------|-------|
| `redis_url` | `str \| None` | `None` | `YOKEDCACHE_REDIS_URL` | Falls back to memory backend if `None` |
| `max_connections` | `int` | `50` | `YOKEDCACHE_MAX_CONNECTIONS` | Redis connection pool size |
| `connection_timeout` | `int` | `30` | `YOKEDCACHE_CONNECTION_TIMEOUT` | Seconds |
| `connection_pool_kwargs` | `dict` | `{}` | — | Passed directly to `redis-py` |

**`redis_url` formats:**

```
redis://localhost:6379/0
redis://:password@host:6379/0
redis://username:password@host:6379/0
rediss://host:6380/0                          ← TLS
redis+sentinel://s1:26379,s2:26379/master/0  ← Sentinel
```

**`connection_pool_kwargs` common options:**

```python
connection_pool_kwargs={
    "socket_connect_timeout": 5,    # seconds to establish connection
    "socket_timeout": 5,            # seconds for read/write operations
    "socket_keepalive": True,       # keep idle connections alive
    "retry_on_timeout": True,       # retry on socket timeout
    "health_check_interval": 30,    # background connection health ping (s)
    "ssl_cert_reqs": "required",    # TLS cert validation
    "ssl_ca_certs": "/path/to/ca",  # CA certificate path
}
```

---

### Cache behavior

| Field | Type | Default | Env var |
|-------|------|---------|---------|
| `default_ttl` | `int` | `300` | `YOKEDCACHE_DEFAULT_TTL` |
| `key_prefix` | `str` | `"yokedcache"` | `YOKEDCACHE_KEY_PREFIX` |
| `default_serialization` | `SerializationMethod` | `JSON` | `YOKEDCACHE_DEFAULT_SERIALIZATION` |
| `ttl_jitter_percent` | `float` | `10.0` | — |
| `allow_legacy_insecure_deserialization` | `bool` | `True` | — |

**`ttl_jitter_percent`:** Adds randomness to TTL to prevent cache stampedes. At `10.0`, a 300s TTL becomes 270–330s. Set to `0` to disable.

**`allow_legacy_insecure_deserialization`:** Set to `False` once you've migrated away from 0.x cache entries. Improves security by rejecting blobs that weren't written with the typed envelope format introduced in 1.0.0.

---

### Resilience

| Field | Type | Default | Env var |
|-------|------|---------|---------|
| `fallback_enabled` | `bool` | `True` | `YOKEDCACHE_FALLBACK_ENABLED` |
| `connection_retries` | `int` | `3` | `YOKEDCACHE_CONNECTION_RETRIES` |
| `retry_delay` | `float` | `0.1` | — |
| `enable_circuit_breaker` | `bool` | `False` | `YOKEDCACHE_ENABLE_CIRCUIT_BREAKER` |
| `circuit_breaker_failure_threshold` | `int` | `5` | — |
| `circuit_breaker_timeout` | `float` | `60.0` | — |

See [Resilience](resilience.md) for detailed behavior.

---

### Memory backend

| Field | Type | Default |
|-------|------|---------|
| `memory_max_size` | `int` | `10000` |
| `memory_cleanup_interval` | `int` | `300` |

Only applies when no `redis_url` is set.

---

### Features

| Field | Type | Default | Env var |
|-------|------|---------|---------|
| `enable_fuzzy` | `bool` | `False` | `YOKEDCACHE_ENABLE_FUZZY` |
| `fuzzy_threshold` | `int` | `80` | `YOKEDCACHE_FUZZY_THRESHOLD` |
| `enable_compression` | `bool` | `False` | `YOKEDCACHE_ENABLE_COMPRESSION` |
| `compression_threshold` | `int` | `1024` | — |

**Fuzzy search** requires `pip install "yokedcache[fuzzy]"`.
**Compression** uses zlib. Values smaller than `compression_threshold` bytes are not compressed.

---

### Logging

| Field | Type | Default | Env var |
|-------|------|---------|---------|
| `log_level` | `str` | `"INFO"` | `YOKEDCACHE_LOG_LEVEL` |

YokedCache logs under the `yokedcache` logger. To customize:

```python
import logging
logging.getLogger("yokedcache").setLevel(logging.DEBUG)
```

---

### Metrics

| Field | Type | Default | Env var |
|-------|------|---------|---------|
| `enable_metrics` | `bool` | `False` | `YOKEDCACHE_ENABLE_METRICS` |
| `prometheus_port` | `int` | `8000` | `YOKEDCACHE_PROMETHEUS_PORT` |
| `statsd_host` | `str \| None` | `None` | `YOKEDCACHE_STATSD_HOST` |
| `statsd_port` | `int` | `8125` | `YOKEDCACHE_STATSD_PORT` |

---

## Per-table configuration

Different tables can have different TTLs, serialization, tags, and feature settings:

```python
from yokedcache.config import CacheConfig, TableCacheConfig
from yokedcache.models import SerializationMethod

config = CacheConfig(
    default_ttl=300,
    tables={
        "users": TableCacheConfig(
            ttl=3600,                                    # 1 hour (overrides default)
            tags={"user_data"},                          # auto-applied to all reads
            serialization_method=SerializationMethod.JSON,
            enable_fuzzy=True,
            fuzzy_threshold=85,
        ),
        "sessions": TableCacheConfig(
            ttl=900,                                     # 15 min
            tags={"session_data"},
        ),
        "products": TableCacheConfig(
            ttl=7200,                                    # 2 hours
            serialization_method=SerializationMethod.MSGPACK,
            enable_compression=True,
            compression_threshold=512,
        ),
        "analytics": TableCacheConfig(
            ttl=60,                                      # 1 min—fresh data matters
            enable_fuzzy=False,
        ),
    }
)
```

### `TableCacheConfig` fields

| Field | Type | Description |
|-------|------|-------------|
| `ttl` | `int` | TTL for this table (overrides `default_ttl`) |
| `tags` | `set[str]` | Tags automatically applied to all entries for this table |
| `serialization_method` | `SerializationMethod` | Overrides `default_serialization` |
| `enable_fuzzy` | `bool` | Overrides `enable_fuzzy` |
| `fuzzy_threshold` | `int` | Overrides `fuzzy_threshold` |
| `enable_compression` | `bool` | Overrides `enable_compression` |
| `compression_threshold` | `int` | Overrides `compression_threshold` |
| `query_specific_ttls` | `dict[str, int]` | Map specific SQL patterns to TTLs |

**Query-specific TTLs:**

```python
"analytics": TableCacheConfig(
    ttl=300,
    query_specific_ttls={
        "SELECT COUNT(*) FROM analytics": 30,       # count is cheap to refresh
        "SELECT * FROM analytics WHERE date = ?": 3600,  # historical data is stable
    },
)
```

---

## Environment-specific configs

A clean pattern for dev/staging/prod:

```python
import os
from yokedcache import YokedCache
from yokedcache.config import CacheConfig

env = os.getenv("ENV", "development")

configs = {
    "development": CacheConfig(
        # No redis_url — use memory for fast local dev
        default_ttl=60,
        key_prefix="dev_myapp",
        log_level="DEBUG",
    ),
    "testing": CacheConfig(
        # Also memory, but separate prefix to avoid polluting dev data
        default_ttl=30,
        key_prefix="test_myapp",
        log_level="WARNING",
    ),
    "production": CacheConfig(
        redis_url=os.environ["REDIS_URL"],
        default_ttl=300,
        key_prefix="prod_myapp",
        max_connections=50,
        enable_circuit_breaker=True,
        allow_legacy_insecure_deserialization=False,
        log_level="WARNING",
        enable_metrics=True,
    ),
}

cache = YokedCache(configs[env])
```

---

## Exporting configuration

Dump the active config for inspection or backup:

```python
config_dict = cache.config.to_dict()
config_yaml = cache.config.to_yaml()
```

CLI:

```bash
yokedcache export-config --output config.yaml
yokedcache export-config --format json
```

---

## Validation

YokedCache validates the config at startup and raises `ConfigValidationError` for invalid values (negative TTL, bad URL format, etc.):

```python
from yokedcache.exceptions import ConfigValidationError

try:
    config = CacheConfig(default_ttl=-1)
except ConfigValidationError as e:
    print(e)  # "default_ttl must be a positive integer"
```
