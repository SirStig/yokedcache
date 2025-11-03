# Configuration Guide

YokedCache offers flexible configuration options to adapt to your specific environment and requirements. This guide covers all configuration methods and options.

## Configuration Methods

### 1. Programmatic Configuration

The most common approach for application integration:

```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.models import SerializationMethod

# Basic configuration
config = CacheConfig(
    redis_url="redis://localhost:6379/0",
    default_ttl=300,
    key_prefix="myapp"
)
cache = YokedCache(config=config)

# Advanced configuration with v0.2.1 features
config = CacheConfig(
    # Connection settings
    redis_url="redis://localhost:6379/0",
    max_connections=50,
    connection_timeout=30,

    # Cache behavior
    default_ttl=300,
    key_prefix="myapp",

    # Features
    enable_fuzzy=True,
    fuzzy_threshold=80,

    # Serialization
    default_serialization=SerializationMethod.JSON,

    # Circuit breaker settings (v0.2.1+)
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_timeout=60.0,

    # Connection pool customization (v0.2.1+)
    connection_pool_kwargs={
        "socket_connect_timeout": 5.0,
        "socket_timeout": 5.0,
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30
    },

    # Error handling and resilience (v0.2.1+)
    fallback_enabled=True,
    connection_retries=3,
    retry_delay=0.1,

    # Logging
    log_level="INFO"
)
cache = YokedCache(config=config)
```

### 2. YAML Configuration

Ideal for deployment environments and external configuration:

```yaml
# cache_config.yaml
redis_url: redis://localhost:6379/0
default_ttl: 300
key_prefix: myapp
max_connections: 50
enable_fuzzy: true
fuzzy_threshold: 80
log_level: INFO

# Table-specific configurations
tables:
  users:
    ttl: 3600
    tags: ["user_data"]
    serialization_method: JSON
    enable_fuzzy: true
    fuzzy_threshold: 85

  products:
    ttl: 1800
    tags: ["product_data", "catalog"]
    serialization_method: PICKLE

  sessions:
    ttl: 900
    tags: ["session_data"]
    serialization_method: JSON
    query_specific_ttls:
      "SELECT * FROM sessions WHERE active = true": 300
      "SELECT * FROM sessions WHERE user_id = ?": 600

# Monitoring configuration
monitoring:
  enable_metrics: true
  prometheus_port: 8000
  statsd_host: "localhost"
  statsd_port: 8125
```

Load YAML configuration:

```python
import yaml
from yokedcache import YokedCache, CacheConfig

# Load from file
with open("cache_config.yaml", "r") as f:
    config_dict = yaml.safe_load(f)

config = CacheConfig.from_dict(config_dict)
cache = YokedCache(config=config)

# Or load directly
cache = YokedCache.from_yaml("cache_config.yaml")
```

### 3. Environment Variables

Perfect for containerized deployments and CI/CD:

```bash
# Basic settings
export YOKEDCACHE_REDIS_URL="redis://localhost:6379/0"
export YOKEDCACHE_DEFAULT_TTL="300"
export YOKEDCACHE_KEY_PREFIX="myapp"

# Connection settings
export YOKEDCACHE_MAX_CONNECTIONS="50"
export YOKEDCACHE_CONNECTION_TIMEOUT="30"

# Feature flags
export YOKEDCACHE_ENABLE_FUZZY="true"
export YOKEDCACHE_FUZZY_THRESHOLD="80"

# Logging
export YOKEDCACHE_LOG_LEVEL="INFO"

# Monitoring
export YOKEDCACHE_ENABLE_METRICS="true"
export YOKEDCACHE_PROMETHEUS_PORT="8000"
```

Use environment variables in code:

```python
from yokedcache import YokedCache

# Automatically loads from environment variables
cache = YokedCache.from_env()

# Or combine with programmatic config
config = CacheConfig.from_env()
config.default_ttl = 600  # Override specific settings
cache = YokedCache(config=config)
```

### 4. Configuration Precedence

When multiple configuration methods are used, values are applied in this order (highest to lowest precedence):

1. **Explicit parameters** passed to methods
2. **Programmatic configuration** via `CacheConfig`
3. **YAML configuration** files
4. **Environment variables**
5. **Default values**

## Configuration Reference

### Core Settings

#### `redis_url` (str)
**Default**: `"redis://localhost:6379/0"`
**Environment**: `YOKEDCACHE_REDIS_URL`

Redis connection string. Supports various formats:

```python
# Basic Redis
"redis://localhost:6379/0"

# With authentication
"redis://:password@localhost:6379/0"
"redis://username:password@localhost:6379/0"

# TLS/SSL
"rediss://localhost:6380/0"

# Sentinel
"redis+sentinel://sentinel1:26379,sentinel2:26379/mymaster/0"

# Cluster
"redis://localhost:7000,localhost:7001,localhost:7002/0"
```

#### `default_ttl` (int)
**Default**: `300`
**Environment**: `YOKEDCACHE_DEFAULT_TTL`

Default time-to-live in seconds for cache entries when no explicit TTL is provided.

#### `key_prefix` (str)
**Default**: `"yokedcache"`
**Environment**: `YOKEDCACHE_KEY_PREFIX`

Prefix added to all cache keys to avoid conflicts with other applications using the same Redis instance.

### Connection Settings

#### `max_connections` (int)
**Default**: `50`
**Environment**: `YOKEDCACHE_MAX_CONNECTIONS`

Maximum number of connections in the Redis connection pool.

#### `connection_timeout` (int)
**Default**: `30`

#### `connection_pool_kwargs` (Dict[str, Any]) *(v0.2.1+)*
**Default**: `{}`

Advanced Redis connection pool configuration options. Allows fine-tuning of Redis connection behavior:

```python
connection_pool_kwargs={
    "socket_connect_timeout": 5.0,  # Connection timeout
    "socket_timeout": 5.0,          # Socket read/write timeout
    "socket_keepalive": True,       # Enable TCP keepalive
    "socket_keepalive_options": {   # Keepalive settings
        "TCP_KEEPIDLE": 1,
        "TCP_KEEPINTVL": 3,
        "TCP_KEEPCNT": 5
    },
    "retry_on_timeout": True,       # Retry on timeout
    "health_check_interval": 30     # Health check frequency
}
```

### Resilience Settings *(v0.2.1+)*

#### `enable_circuit_breaker` (bool)
**Default**: `False`
**Environment**: `YOKEDCACHE_ENABLE_CIRCUIT_BREAKER`

Enable circuit breaker pattern to prevent cascading failures during Redis outages.

#### `circuit_breaker_failure_threshold` (int)
**Default**: `5`

Number of consecutive failures before opening the circuit breaker.

#### `circuit_breaker_timeout` (float)
**Default**: `60.0`

Time in seconds to wait before attempting to close the circuit breaker.

#### `fallback_enabled` (bool)
**Default**: `True`
**Environment**: `YOKEDCACHE_FALLBACK_ENABLED`

Enable graceful fallback behavior when cache operations fail.

#### `connection_retries` (int)
**Default**: `3`
**Environment**: `YOKEDCACHE_CONNECTION_RETRIES`

Number of retry attempts for failed Redis operations.

#### `retry_delay` (float)
**Default**: `0.1`

Base delay between retry attempts (with exponential backoff).
**Environment**: `YOKEDCACHE_CONNECTION_TIMEOUT`

Connection timeout in seconds for Redis operations.

#### `retry_attempts` (int)
**Default**: `3`
**Environment**: `YOKEDCACHE_RETRY_ATTEMPTS`

Number of retry attempts for failed operations.

#### `retry_delay` (float)
**Default**: `1.0`
**Environment**: `YOKEDCACHE_RETRY_DELAY`

Delay in seconds between retry attempts.

### Feature Settings

#### `enable_fuzzy` (bool)
**Default**: `False`
**Environment**: `YOKEDCACHE_ENABLE_FUZZY`

Enable fuzzy search capabilities. Requires `yokedcache[fuzzy]` installation.

#### `fuzzy_threshold` (int)
**Default**: `80`
**Environment**: `YOKEDCACHE_FUZZY_THRESHOLD`

Minimum similarity score (0-100) for fuzzy search matches.

#### `enable_compression` (bool)
**Default**: `False`
**Environment**: `YOKEDCACHE_ENABLE_COMPRESSION`

Enable automatic compression for large cache values.

#### `compression_threshold` (int)
**Default**: `1024`
**Environment**: `YOKEDCACHE_COMPRESSION_THRESHOLD`

Minimum size in bytes before compression is applied.

### Serialization Settings

#### `default_serialization` (SerializationMethod)
**Default**: `SerializationMethod.JSON`
**Environment**: `YOKEDCACHE_DEFAULT_SERIALIZATION`

Default serialization method for cache values:

- `JSON`: Best for simple data types and interoperability
- `PICKLE`: Best for complex Python objects
- `MSGPACK`: Best for binary efficiency

### Logging Settings

#### `log_level` (str)
**Default**: `"INFO"`
**Environment**: `YOKEDCACHE_LOG_LEVEL`

Logging level for YokedCache operations. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`.

#### `log_format` (str)
**Default**: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`
**Environment**: `YOKEDCACHE_LOG_FORMAT`

Custom log format string.

### Monitoring Settings

#### `enable_metrics` (bool)
**Default**: `False`
**Environment**: `YOKEDCACHE_ENABLE_METRICS`

Enable metrics collection for monitoring.

#### `prometheus_port` (int)
**Default**: `8000`
**Environment**: `YOKEDCACHE_PROMETHEUS_PORT`

Port for Prometheus metrics endpoint.

#### `statsd_host` (str)
**Default**: `None`
**Environment**: `YOKEDCACHE_STATSD_HOST`

StatsD host for metrics collection.

#### `statsd_port` (int)
**Default**: `8125`
**Environment**: `YOKEDCACHE_STATSD_PORT`

StatsD port for metrics collection.

## Table-Specific Configuration

Configure different behaviors for different data types:

```python
from yokedcache import CacheConfig, TableCacheConfig
from yokedcache.models import SerializationMethod

config = CacheConfig(
    default_ttl=300,
    tables={
        "users": TableCacheConfig(
            ttl=3600,                                    # Longer TTL for user data
            tags={"user_data"},                         # Default tags
            serialization_method=SerializationMethod.JSON,
            enable_fuzzy=True,
            fuzzy_threshold=85,

            # Query-specific TTL overrides
            query_specific_ttls={
                "SELECT * FROM users WHERE active = true": 600,
                "SELECT COUNT(*) FROM users": 60
            }
        ),

        "products": TableCacheConfig(
            ttl=1800,
            tags={"product_data", "catalog"},
            serialization_method=SerializationMethod.PICKLE,
            enable_compression=True,
            compression_threshold=512
        ),

        "sessions": TableCacheConfig(
            ttl=900,                                    # Short TTL for sessions
            tags={"session_data"},
            serialization_method=SerializationMethod.JSON,
            enable_fuzzy=False                          # Disable fuzzy for sessions
        )
    }
)
```

### TableCacheConfig Options

#### `ttl` (int)
Override default TTL for this table.

#### `tags` (set[str])
Default tags applied to all cache entries for this table.

#### `serialization_method` (SerializationMethod)
Override default serialization method for this table.

#### `enable_fuzzy` (bool)
Override global fuzzy search setting for this table.

#### `fuzzy_threshold` (int)
Override global fuzzy threshold for this table.

#### `query_specific_ttls` (dict[str, int])
Map of SQL query patterns to specific TTL values.

#### `enable_compression` (bool)
Override global compression setting for this table.

#### `compression_threshold` (int)
Override global compression threshold for this table.

## Backend-Specific Configuration

### Redis Configuration

```python
from yokedcache import CacheConfig
from yokedcache.backends import RedisBackend

# Advanced Redis configuration
redis_config = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": "secret",
    "ssl": True,
    "ssl_cert_reqs": "required",
    "socket_connect_timeout": 30,
    "socket_timeout": 30,
    "retry_on_timeout": True,
    "health_check_interval": 30
}

backend = RedisBackend(**redis_config)
config = CacheConfig(backend=backend)
cache = YokedCache(config=config)
```

### Memory Backend Configuration

```python
from yokedcache.backends import MemoryBackend

# Memory backend for development/testing
backend = MemoryBackend(
    max_size=10000,        # Maximum number of entries
    max_memory_mb=512,     # Maximum memory usage in MB
    eviction_policy="LRU"  # LRU, LFU, or FIFO
)

config = CacheConfig(backend=backend)
cache = YokedCache(config=config)
```

### Memcached Configuration

```python
from yokedcache.backends import MemcachedBackend

# Memcached backend
backend = MemcachedBackend(
    servers=["localhost:11211", "localhost:11212"],
    binary_protocol=True,
    username="myuser",
    password="mypassword"
)

config = CacheConfig(backend=backend)
cache = YokedCache(config=config)
```

## Environment-Specific Configurations

### Development Environment

```yaml
# config/development.yaml
redis_url: redis://localhost:6379/0
default_ttl: 60          # Short TTL for quick testing
key_prefix: dev_myapp
enable_fuzzy: true
log_level: DEBUG         # Verbose logging

tables:
  users:
    ttl: 300
    tags: ["user_data"]
```

### Staging Environment

```yaml
# config/staging.yaml
redis_url: redis://staging-redis:6379/0
default_ttl: 300
key_prefix: staging_myapp
enable_fuzzy: true
log_level: INFO
max_connections: 25

monitoring:
  enable_metrics: true
  prometheus_port: 8000
```

### Production Environment

```yaml
# config/production.yaml
redis_url: rediss://prod-redis.example.com:6380/0
default_ttl: 600
key_prefix: prod_myapp
enable_fuzzy: false      # Disable for performance
log_level: WARNING
max_connections: 100
connection_timeout: 10
retry_attempts: 5

# Compression for large values
enable_compression: true
compression_threshold: 1024

monitoring:
  enable_metrics: true
  prometheus_port: 8000
  statsd_host: "statsd.example.com"
  statsd_port: 8125

tables:
  users:
    ttl: 3600
    tags: ["user_data"]
    enable_compression: true

  products:
    ttl: 7200           # Long TTL for stable product data
    tags: ["product_data"]
    serialization_method: MSGPACK  # Efficient binary format
```

## Configuration Validation

YokedCache validates configuration at startup:

```python
from yokedcache import CacheConfig, ConfigValidationError

try:
    config = CacheConfig(
        default_ttl=-1,  # Invalid: negative TTL
        redis_url="invalid://url"  # Invalid: bad URL format
    )
except ConfigValidationError as e:
    print(f"Configuration error: {e}")

# Validate configuration manually
config = CacheConfig(default_ttl=300)
validation_errors = config.validate()
if validation_errors:
    for error in validation_errors:
        print(f"Validation error: {error}")
```

## Dynamic Configuration Updates

Update configuration at runtime:

```python
# Initial configuration
cache = YokedCache(CacheConfig(default_ttl=300))

# Update configuration
new_config = CacheConfig(
    default_ttl=600,
    enable_fuzzy=True
)
await cache.update_config(new_config)

# Update specific settings
await cache.update_setting("default_ttl", 900)
await cache.update_table_config("users", TableCacheConfig(ttl=7200))
```

## Configuration Export

Export current configuration for backup or deployment:

```python
# Export to YAML
config_yaml = cache.config.to_yaml()
with open("exported_config.yaml", "w") as f:
    f.write(config_yaml)

# Export to dict
config_dict = cache.config.to_dict()

# CLI export
# yokedcache export-config --output config.yaml
```

## Best Practices

### Security
- Use TLS (`rediss://`) for production Redis connections
- Store sensitive configuration in environment variables or secret management systems
- Use different key prefixes for different environments
- Rotate Redis passwords regularly

### Performance
- Set appropriate connection pool sizes based on application concurrency
- Use compression for large cache values
- Choose serialization methods based on data types and performance requirements
- Configure table-specific TTLs based on data volatility

### Monitoring
- Enable metrics in production environments
- Use appropriate log levels (WARNING/ERROR for production)
- Monitor cache hit rates and performance metrics
- Set up alerts for cache failures

### Environment Management
- Use separate configuration files for each environment
- Validate configuration in CI/CD pipelines
- Document configuration changes
- Use configuration templates for consistency

This comprehensive configuration guide should help you set up YokedCache optimally for your specific environment and requirements.
