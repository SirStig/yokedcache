# Keys & Serialization

## Key building

- Library prefixes all keys with `CacheConfig.key_prefix` (default `yokedcache`).
- Function caching uses a stable hash of bound arguments.
- DB query caching builds keys from method name and hashed args.
- `sanitize_key()` ensures Redis-safe characters, shortens overly long keys.

```python
from yokedcache.utils import generate_cache_key

key = generate_cache_key(
    prefix="myapp",
    table="users",
    query="select * from users where id=:id",
    params={"id": 1},
)
```

## TTL and jitter

- Default TTL: `CacheConfig.default_ttl`.
- Jitter: `calculate_ttl_with_jitter(ttl, jitter_percent=10.0)` applied to spread load.

## Serialization

- Default: JSON (`SerializationMethod.JSON`), with custom encoder for sets/datetimes.
- Alternatives: PICKLE, MSGPACK (if installed).

```python
from yokedcache.models import SerializationMethod
await cache.set("key", value, serialization=SerializationMethod.PICKLE)
```

Choose JSON for interoperability; PICKLE for Python-only complex objects; MSGPACK for compact binary.

