# Redis Setup

YokedCache uses Redis. Here are common setups:

## Local (Docker)

```bash
docker run -d --name redis -p 6379:6379 redis:7
```

Then use `redis://localhost:6379/0`.

## Local (Windows/Mac/Linux)

- Install Redis via your package manager or `brew install redis` (macOS).
- Start Redis and connect with `redis-cli ping`.

## Cloud providers

- AWS ElastiCache, Azure Cache for Redis, GCP Memorystore.
- Use the provided connection string, e.g. `rediss://user:pass@host:port/0`.

## TLS

Use `rediss://` for TLS. Example:

```python
from yokedcache import YokedCache
cache = YokedCache(redis_url="rediss://user:pass@my-redis.example.com:6380/0")
```

## Connectivity checklist

- Security groups/firewalls allow Redis port.
- Credentials are correct; for ACL users include username.
- Prefer a low-latency region to your app.
