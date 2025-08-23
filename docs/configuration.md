# Configuration

YokedCache can be configured programmatically or via YAML.

## YAML example

```yaml
# cache_config.yaml
redis_url: redis://localhost:6379/0
default_ttl: 300
key_prefix: yokedcache
enable_fuzzy: false

tables:
  users:
    ttl: 3600
    tags: ["user_data"]
    invalidation_rules:
      - table: users
        on: [update, delete]
        invalidate_tags: ["user_data"]
```

## Programmatic

```python
from yokedcache import CacheConfig, YokedCache

config = CacheConfig(default_ttl=600, key_prefix="myapp")
cache = YokedCache(config=config)
```

## Environment variables

- `YOKEDCACHE_REDIS_URL`
- `YOKEDCACHE_DEFAULT_TTL`
- `YOKEDCACHE_KEY_PREFIX`
- `YOKEDCACHE_ENABLE_FUZZY`
- `YOKEDCACHE_FUZZY_THRESHOLD`
