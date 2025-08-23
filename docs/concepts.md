# Concepts

- **Cache keys**: Namespaced identifiers for cached values. Built from `key_prefix`, function/table context, and hashed args.
- **TTL and jitter**: Each entry expires after TTL; jitter spreads expirations to avoid thundering herds.
- **Tags**: Group keys for bulk invalidation, e.g., `table:users`.
- **Auto-invalidation**: Write operations trigger targeted cache clears.
- **Serialization**: Values are serialized (JSON by default) before storage.
- **Metrics**: Hit/miss counts, latencies, memory usage via `get_stats()` and CLI.

## Where concepts live in code

- Keys: `yokedcache.utils.generate_cache_key`, `sanitize_key`
- TTL jitter: `yokedcache.utils.calculate_ttl_with_jitter`
- Tags: maintained via Redis sets, see `YokedCache._add_tags_to_key`
- Auto-invalidation: `CachedDatabaseWrapper` in `yokedcache.decorators`
- Serialization: `yokedcache.utils.serialize_data` / `deserialize_data`
- Config: `yokedcache.config.CacheConfig`
