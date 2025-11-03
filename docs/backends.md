# Multi-Backend Architecture

YokedCache 0.2.0 introduces a flexible multi-backend architecture that allows you to choose the best caching solution for your specific needs. Whether you need the speed of in-memory caching, the persistence of Redis, or the simplicity of Memcached, YokedCache provides a unified interface.

## Table of Contents

- [Overview](#overview)
- [Available Backends](#available-backends)
- [Backend Selection](#backend-selection)
- [Configuration](#configuration)
- [Performance Characteristics](#performance-characteristics)
- [Migration Guide](#migration-guide)

## Overview

The multi-backend system is built around a common `CacheBackend` interface that ensures consistent behavior across all implementations. This means you can switch between backends without changing your application code.

### Key Benefits

- **Flexibility**: Choose the right backend for each use case
- **Consistency**: Unified API across all backends
- **Performance**: Optimized implementations for each backend type
- **Scalability**: Easy backend switching as requirements change
- **Testing**: Use memory backend for tests, Redis for production

## Available Backends

### Memory Backend

In-memory caching with LRU eviction and TTL support.

**Use Cases:**
- Single-server applications
- Development and testing
- Fast access to frequently used data
- When data persistence is not required

**Features:**
- Thread-safe operations
- LRU eviction when max size reached
- TTL expiration support
- Tag-based invalidation
- Pattern-based invalidation
- Fuzzy search capabilities

**Configuration:**
```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import MemoryBackend

# Basic configuration
config = CacheConfig(
    backend=MemoryBackend(
        max_size=10000,        # Maximum number of keys
        key_prefix="myapp"
    )
)

cache = YokedCache(config)
```

**Advanced Configuration:**
```python
backend = MemoryBackend(
    max_size=50000,
    key_prefix="prod",
    default_ttl=3600,         # 1 hour default TTL
    cleanup_interval=300      # Clean expired keys every 5 minutes
)
```

### Redis Backend

Distributed caching with Redis for scalable applications.

**Use Cases:**
- Multi-server applications
- Shared cache across services
- High availability requirements
- Large datasets that don't fit in memory

**Features:**
- Connection pooling
- Persistence options
- Clustering support
- Pub/sub capabilities
- Advanced data structures
- Production-ready reliability

**Configuration:**
```python
from yokedcache.backends import RedisBackend

# Basic Redis configuration
backend = RedisBackend(
    redis_url="redis://localhost:6379/0",
    key_prefix="myapp",
    connection_pool_size=20
)

# With authentication and SSL
backend = RedisBackend(
    redis_url="rediss://username:password@redis.example.com:6380/0",
    key_prefix="secure_app",
    ssl_cert_reqs="required",
    ssl_ca_certs="/path/to/ca-certificates.crt"
)
```

**Connection Options:**
```python
backend = RedisBackend(
    host="localhost",
    port=6379,
    db=0,
    password="secret",
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
    health_check_interval=30
)
```

### Memcached Backend

Lightweight, distributed memory caching system.

**Use Cases:**
- Simple key-value caching
- Legacy system integration
- When you need a proven, stable solution
- Memory-constrained environments

**Features:**
- Lightweight protocol
- Automatic load balancing
- Consistent hashing
- Binary protocol support
- Multi-server support

**Configuration:**
```python
from yokedcache.backends import MemcachedBackend

# Single server
backend = MemcachedBackend(
    servers=["localhost:11211"],
    key_prefix="myapp"
)

# Multiple servers with weights
backend = MemcachedBackend(
    servers=[
        ("cache1.example.com:11211", 3),  # Weight 3
        ("cache2.example.com:11211", 1),  # Weight 1
    ],
    binary=True,              # Use binary protocol
    behaviors={
        "tcp_nodelay": True,
        "ketama": True,       # Consistent hashing
    }
)
```

## Backend Selection

### Decision Matrix

| Feature | Memory | Redis | Memcached |
|---------|--------|-------|-----------|
| **Performance** | Excellent | Very Good | Very Good |
| **Persistence** | None | Optional | None |
| **Distribution** | Single Node | Multi-Node | Multi-Node |
| **Memory Usage** | Process RAM | Dedicated | Dedicated |
| **Complexity** | Low | Medium | Low |
| **Features** | Basic | Advanced | Basic |

### Performance Characteristics

#### Memory Backend
- **Latency**: < 1μs
- **Throughput**: 1M+ ops/sec
- **Memory**: Uses process heap
- **Scalability**: Single process only

#### Redis Backend
- **Latency**: 0.1-1ms (local), 1-10ms (network)
- **Throughput**: 100K+ ops/sec
- **Memory**: Dedicated Redis memory
- **Scalability**: Horizontal with clustering

#### Memcached Backend
- **Latency**: 0.5-2ms (network)
- **Throughput**: 50K+ ops/sec
- **Memory**: Dedicated Memcached memory
- **Scalability**: Horizontal with consistent hashing

## Configuration

### Environment-Based Configuration

```python
import os
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import MemoryBackend, RedisBackend

def create_cache():
    """Create cache based on environment."""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "development":
        backend = MemoryBackend(max_size=1000)
    elif env == "testing":
        backend = MemoryBackend(max_size=100)
    else:  # production
        backend = RedisBackend(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            connection_pool_size=int(os.getenv("REDIS_POOL_SIZE", "20"))
        )

    config = CacheConfig(backend=backend)
    return YokedCache(config)
```

### YAML Configuration

```yaml
# config.yaml
cache:
  development:
    backend: memory
    memory:
      max_size: 1000
      key_prefix: "dev"

  production:
    backend: redis
    redis:
      url: "redis://prod-redis:6379/0"
      pool_size: 50
      key_prefix: "prod"

  testing:
    backend: memory
    memory:
      max_size: 100
      key_prefix: "test"
```

Loading YAML configuration:
```python
import yaml
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import MemoryBackend, RedisBackend

def load_cache_from_config(config_file: str, environment: str):
    """Load cache configuration from YAML file."""
    with open(config_file) as f:
        config = yaml.safe_load(f)

    cache_config = config["cache"][environment]
    backend_type = cache_config["backend"]

    if backend_type == "memory":
        backend = MemoryBackend(**cache_config["memory"])
    elif backend_type == "redis":
        backend = RedisBackend(**cache_config["redis"])
    else:
        raise ValueError(f"Unknown backend: {backend_type}")

    return YokedCache(CacheConfig(backend=backend))
```

### Runtime Backend Switching

```python
class AdaptiveCache:
    """Cache that can switch backends at runtime."""

    def __init__(self):
        self.memory_backend = MemoryBackend(max_size=1000)
        self.redis_backend = RedisBackend()
        self.current_backend = self.memory_backend

    async def switch_to_redis(self):
        """Switch to Redis backend."""
        await self.current_backend.disconnect()
        await self.redis_backend.connect()
        self.current_backend = self.redis_backend

    async def switch_to_memory(self):
        """Switch to memory backend."""
        await self.current_backend.disconnect()
        await self.memory_backend.connect()
        self.current_backend = self.memory_backend

    async def get(self, key: str):
        """Get value using current backend."""
        return await self.current_backend.get(key)
```

## Migration Guide

### From Single Backend to Multi-Backend

**Before (v0.1.x):**
```python
from yokedcache import YokedCache, CacheConfig

config = CacheConfig(redis_url="redis://localhost:6379/0")
cache = YokedCache(config)
```

**After (v0.2.0):**
```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import RedisBackend

backend = RedisBackend(redis_url="redis://localhost:6379/0")
config = CacheConfig(backend=backend)
cache = YokedCache(config)
```

### Migrating Data Between Backends

```python
async def migrate_cache_data(source_backend, target_backend):
    """Migrate data from one backend to another."""
    await source_backend.connect()
    await target_backend.connect()

    try:
        # Get all keys from source
        keys = await source_backend.get_all_keys("*")

        migrated = 0
        for key in keys:
            value = await source_backend.get(key)
            if value is not None:
                await target_backend.set(key, value)
                migrated += 1

        print(f"Migrated {migrated} keys successfully")

    finally:
        await source_backend.disconnect()
        await target_backend.disconnect()

# Example usage
memory_backend = MemoryBackend()
redis_backend = RedisBackend()

await migrate_cache_data(memory_backend, redis_backend)
```

## Best Practices

### Development Workflow

1. **Use Memory Backend for Tests**
   ```python
   @pytest.fixture
   async def cache():
       backend = MemoryBackend(max_size=100)
       config = CacheConfig(backend=backend)
       cache = YokedCache(config)
       await cache.connect()
       yield cache
       await cache.disconnect()
   ```

2. **Environment-Specific Backends**
   - Development: Memory backend for fast iteration
   - Testing: Memory backend for isolation
   - Staging: Redis backend to match production
   - Production: Redis backend with proper configuration

3. **Backend Health Monitoring**
   ```python
   async def check_backend_health(backend):
       """Check if backend is healthy."""
       try:
           return await backend.health_check()
       except Exception as e:
           logger.error(f"Backend health check failed: {e}")
           return False
   ```

4. **Graceful Degradation**
   ```python
   class ResilientCache:
       def __init__(self):
           self.primary = RedisBackend()
           self.fallback = MemoryBackend(max_size=1000)

       async def get(self, key: str):
           try:
               return await self.primary.get(key)
           except Exception:
               logger.warning("Primary backend failed, using fallback")
               return await self.fallback.get(key)
   ```

### Production Considerations

1. **Connection Pooling**: Use appropriate pool sizes for Redis
2. **Memory Management**: Monitor memory usage for all backends
3. **Error Handling**: Implement proper error handling and fallbacks
4. **Monitoring**: Use the monitoring features to track backend performance
5. **Backup Strategies**: Plan for data backup with persistent backends

## Redis Setup & Configuration

### Local Development

#### Using Docker (Recommended)

```bash
# Basic Redis setup
docker run -d --name redis -p 6379:6379 redis:7

# Redis with persistence
docker run -d --name redis -p 6379:6379 \
  -v redis-data:/data redis:7 redis-server --appendonly yes
```

Then connect with `redis://localhost:6379/0`.

#### Native Installation

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt install redis-server
sudo systemctl start redis-server
```

**Windows:**
Use Docker or WSL2 with Linux installation.

**Verify Installation:**
```bash
redis-cli ping
# Should return: PONG
```

### Production Deployment

#### Cloud Providers

**AWS ElastiCache:**
- Create Redis cluster in ElastiCache
- Use cluster endpoint: `redis://cluster.abc123.cache.amazonaws.com:6379`
- Enable encryption in transit: `rediss://cluster.abc123.cache.amazonaws.com:6380`

**Azure Cache for Redis:**
- Create Redis instance in Azure portal
- Use primary connection string: `rediss://cache-name.redis.cache.windows.net:6380`

**Google Cloud Memorystore:**
- Create Redis instance in GCP console
- Use internal IP: `redis://10.0.0.3:6379`

#### TLS/SSL Configuration

For encrypted connections, use the `rediss://` protocol:

```python
from yokedcache import YokedCache, CacheConfig

# TLS configuration
config = CacheConfig(
    redis_url="rediss://user:pass@my-redis.example.com:6380/0",
    connection_pool_kwargs={
        "ssl_cert_reqs": "required",
        "ssl_ca_certs": "/path/to/ca.crt",
        "ssl_check_hostname": True
    }
)

cache = YokedCache(config=config)
```

#### Authentication

**Password Authentication:**
```python
config = CacheConfig(
    redis_url="redis://:mypassword@localhost:6379/0"
)
```

**Username/Password (Redis 6+):**
```python
config = CacheConfig(
    redis_url="redis://username:password@localhost:6379/0"
)
```

**ACL Configuration:**
```redis
# Create user for YokedCache
ACL SETUSER yokedcache_user on >password123 +@all ~*
```

### Performance Tuning

#### Redis Configuration

Add these settings to `redis.conf`:

```redis
# Memory optimization
maxmemory 2gb
maxmemory-policy allkeys-lru

# Network optimization
tcp-keepalive 300
timeout 0

# Persistence (optional)
save 900 1
save 300 10
save 60 10000

# Performance
tcp-nodelay yes
```

#### Connection Pool Tuning

```python
config = CacheConfig(
    redis_url="redis://localhost:6379/0",
    max_connections=100,
    connection_pool_kwargs={
        "socket_keepalive": True,
        "socket_keepalive_options": {
            "TCP_KEEPIDLE": 1,
            "TCP_KEEPINTVL": 3,
            "TCP_KEEPCNT": 5
        },
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
        "health_check_interval": 30
    }
)
```

### Connectivity Troubleshooting

#### Pre-deployment Checklist

- [ ] **Network Access**: Security groups/firewalls allow Redis port (6379/6380)
- [ ] **DNS Resolution**: Hostname resolves correctly from application servers
- [ ] **Authentication**: Credentials are correct and user has necessary permissions
- [ ] **TLS**: Certificate validation passes for SSL connections
- [ ] **Latency**: Network latency is acceptable (<10ms preferred)
- [ ] **Memory**: Redis has sufficient memory for expected cache size

#### Connection Testing

```python
import redis
import asyncio
from yokedcache import YokedCache

async def test_connection():
    try:
        cache = YokedCache(redis_url="redis://localhost:6379/0")

        # Test basic connectivity
        health = await cache.health()
        print(f"Health check: {health}")

        # Test operations
        await cache.set("test_key", "test_value", ttl=60)
        value = await cache.get("test_key")
        print(f"Test operation: {value}")

        # Test detailed health check
        detailed = await cache.detailed_health_check()
        print(f"Detailed health: {detailed}")

    except Exception as e:
        print(f"Connection failed: {e}")

# Run test
asyncio.run(test_connection())
```

#### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Connection refused | Redis not running | Start Redis service |
| Authentication failed | Wrong credentials | Check username/password |
| SSL handshake failed | Certificate issues | Verify TLS configuration |
| Timeout errors | Network latency | Increase timeouts, check network |
| Memory errors | Redis out of memory | Increase Redis memory limit |

---

For more information about specific backend implementations and advanced configuration options, see the API documentation for each backend class.
