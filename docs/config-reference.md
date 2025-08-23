# Configuration Reference

Key options from `CacheConfig`:

- `redis_url` (str): Redis connection string. Default `redis://localhost:6379/0`.
- `default_ttl` (int): Default TTL seconds. Default `300`.
- `key_prefix` (str): Prefix for all keys. Default `yokedcache`.
- `enable_fuzzy` (bool): Enable fuzzy search. Default `False`.
- `fuzzy_threshold` (int): 0-100 score cutoff. Default `80`.
- `max_connections` (int): Redis pool size. Default `50`.
- `log_level` (str): Logging level. Default `INFO`.

Table-level via `TableCacheConfig`:

- `ttl` (int): Per-table TTL.
- `tags` (set[str]): Default tags applied to reads.
- `enable_fuzzy` (bool), `fuzzy_threshold` (int)
- `serialization_method`: JSON/PICKLE/MSGPACK
- `query_specific_ttls` (dict[str,int]): per-query-hash TTL overrides.

Env overrides:

- `YOKEDCACHE_REDIS_URL`, `YOKEDCACHE_DEFAULT_TTL`, `YOKEDCACHE_KEY_PREFIX`,
  `YOKEDCACHE_ENABLE_FUZZY`, `YOKEDCACHE_FUZZY_THRESHOLD`, `YOKEDCACHE_MAX_CONNECTIONS`, `YOKEDCACHE_LOG_LEVEL`.
