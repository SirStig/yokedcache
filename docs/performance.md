# Performance

## Redis

- Use a dedicated Redis instance; avoid shared noisy neighbors.
- Increase `max_connections` for high concurrency.
- Prefer cluster or read replicas for scale.

## TTL & jitter

- Tune TTL per table: hot data short TTL; cold data longer.
- Keep jitter (default 10%) to avoid synchronized expirations.

## Keys

- Keep keys compact but descriptive.
- Avoid storing huge values; consider pagination or partial caching.

## Serialization

- JSON is portable; PICKLE/MSGPACK can be faster for complex types.
- Benchmark with realistic payloads.

## Async usage

- Reuse a single `YokedCache` instance; avoid reconnecting per request.
- Use pipeline where appropriate (handled internally for set/tag ops).
