# Troubleshooting & FAQ

## Common issues

### Cache not updating after writes
- Ensure you use `cached_dependency` and call `commit()` to trigger invalidation.
- Pass `table_name` when wrapping the dependency.

### Redis connection errors
- Verify `redis_url` and network connectivity.
- Test with `yokedcache ping`.

### Serialization errors
- Switch serialization: `SerializationMethod.PICKLE`.
- Ensure objects are JSON-serializable or provide custom encoders.

### Keys not found
- Confirm `key_prefix` matches in producer/consumer.
- Check tags and patterns when invalidating.

## FAQ

- How do I disable caching for a route? Call the underlying function directly or set `ttl=0`.
- How do I warm the cache? Use `warm_cache` helper or CLI `warm` with a config file.
- Does it work without FastAPI? Yes, use `@cached` and `YokedCache` directly.
