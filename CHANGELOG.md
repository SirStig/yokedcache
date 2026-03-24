# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-23

First stable 1.x release. Published as **1.0.0** (not a PEP 440 pre-release) so a plain `pip install yokedcache` resolves to this line ahead of 0.x. Focus: security hardening, safer Redis usage, and clearer HTTP cache semantics.

### Security

- Replaced use of `eval()` when loading vector metadata from Redis with `orjson` / `ast.literal_eval`, shape validation, and `numpy.dtype` validation for `RedisVectorSearch.get_vector`.
- Introduced a versioned binary envelope for cache values (`serialize_for_cache` / `deserialize_from_cache`) so reads use a single deserialization path; avoids ambiguous JSON-then-pickle fallback on new payloads.
- Added `CacheConfig.allow_legacy_insecure_deserialization` (default `True`) to allow reading legacy unwrapped blobs during migration; set to `False` when Redis is strictly trusted and legacy entries are gone.
- Documented that `HTTPCacheMiddleware` must not cache per-user responses without a custom `key_builder`; default keys are only method + path (+ optional query).

### Added

- `serialize_for_cache` and `deserialize_from_cache` in `yokedcache.utils` (re-exported from `yokedcache`).
- `CacheConfig.max_single_flight_locks` with bounded LRU-style eviction for single-flight locks.
- `HTTPCacheMiddleware` optional `key_builder(scope) -> str` for cache key control.
- `redis_scan_keys`, `redis_scan_keys_max`, and `redis_delete_keys` helpers for non-blocking iteration and batched deletes.
- `tests` helpers and mocks updated for Redis `SCAN` (`scan_iter`) instead of `KEYS`.

### Changed

- **Minimum Python is now 3.10** (was 3.9). Python 3.9 is EOL; raising the floor lets the lockfile use **filelock** ≥3.25.2 (fixes symlink / TOCTOU issues in older releases). **Supported and CI-tested:** 3.10–3.14. **Python 3.9** installs should stay on **`yokedcache==0.3.0`** (or any `0.3.x`); that line does not receive the 1.x security or dependency hardening—upgrade Python and yokedcache when you can (see docs site *Getting started* and `SECURITY.md`).
- **black** 26.3.1 in dev / pre-commit (CVE-2026-32274: cache path handling).
- **orjson** minimum raised to **≥3.11.6** (addresses unbounded recursion in `loads`/`dumps` on deeply nested JSON in earlier 3.x lines).
- Redis pattern flush, invalidation, fuzzy key listing, and CLI `list` use `SCAN` / `scan_iter` instead of `KEYS`.
- Long cache keys: `sanitize_key` now uses full-length SHA-256 for the hashed suffix (replacing truncated MD5).
- `PrefixRouter.invalidate_pattern` selects the backend using the same longest-prefix rule as `get_backend`.
- Memcached backend reads/writes use the same envelope helpers as Redis for consistency.
- In-memory Redis fallback (`_InMemoryRedis`) implements `scan_iter` for compatibility with scan-based code paths.
- `DiskCacheBackend` creates the thread pool on `connect` and shuts down the executor on `disconnect`.
- `HTTPCacheMiddleware` normalizes `If-None-Match` (quoted tokens, `*`, comma-separated lists) for 304 handling.
- Replaced stdlib `json` with `orjson` for JSON cache payloads, key hashing, decorators, vector metadata fields, and CLI `--format json` output; dependency `orjson>=3.11.6`. Rationale: `orjson` is a fast native-backed serializer, and these paths run on every JSON cache hit/miss and during key construction, so reducing serialization cost improves throughput versus pure-Python `json`.

### Fixed

- `test_backends.TestMemcachedBackend` skip condition: use `MEMCACHED_AVAILABLE` instead of a broken `dir()` check so tests run when `aiomcache` is installed.
- Integration fallback test: use `enable_memory_fallback`, `.invalid` host, and `connect()` so assertions are deterministic without `pytest.skip`.
- CLI and health-check tests: mock `scan_iter` where the implementation uses `redis_scan_keys_max` / `redis_scan_keys`.

## [0.3.0] - 2025-08-26

### Added

- HTTP response caching middleware (ETag, Cache-Control, 304).
- Single-flight protection, stale-while-revalidate, stale-if-error.
- DiskCache and SQLite backends; per-prefix routing to multiple backends.
- OpenTelemetry hooks, cache metrics, optional dependency groups (`disk`, `tracing`, `full`).

### Changed

- SWR scheduler, prefix router, and extended `CacheConfig` for advanced features.

## [0.2.4] - 2025-11-02

### Fixed

- Implemented missing `_handle_tags` and related tag handling.
- Replaced incorrect `CircuitBreakerOpenError` references with `CircuitBreakerError`.
- Removed duplicate / misplaced `YokedCache` methods (`_direct_*`, routing helpers); corrected `self` usage.
- Metrics: use `record_operation` / `OperationMetric`; guard when metrics disabled.
- Circuit breaker: async context manager support (`__aenter__` / `__aexit__`).

## [0.2.3] - 2025-08-25

### Added

- Manual release workflow improvements (prerelease option, version checks).

### Fixed

- `CacheConfig` version retrieval and error handling; FastAPI example typing and errors.

### Changed

- CI, Codecov, pre-commit, docs, and dependency maintenance.

## [0.2.1] - 2025-08-23

### Added

- Circuit breaker, connection pool tuning, retry with backoff, expanded metrics and health reporting.
- Sync/async cache method variants and improved `cached_dependency` for FastAPI generators.
- Timezone-aware datetimes in serialization paths.

### Fixed

- `connection_pool_kwargs` validation; sync-in-async Task issues; generator dependencies; env override parsing; mypy and Windows test stability.

## [0.2.0] - 2024-01-15

### Added

- Pluggable backends (Redis, Memcached, memory), vector similarity search, Prometheus/StatsD hooks, CSV CLI export, LRU memory backend.

### Changed

- Refactored cache around backend abstraction; expanded configuration and documentation.

### Fixed

- Timezone-aware `datetime` usage; optional import fallbacks; vector Manhattan distance; async test stability.

## [0.1.3] - 2025-08-22

### Added

- `python -m yokedcache` entry point; full CLI command set; documentation updates.

### Changed

- CLI architecture and GitHub Actions reliability.

### Fixed

- Redis async close compatibility; async CLI registration; formatting and typing fixes.

### Removed

- Codecov integration (temporary) due to rate limits.

## [0.1.2] - 2025-08-22

### Added

- Initial public structure: Redis caching, invalidation, tags, patterns, fuzzy search, FastAPI integration, YAML config, CLI, metrics, serialization options, async API, pooling, tests, docs, examples, pre-commit, CI.

## [0.1.0] - 2024-01-01

### Added

- Initial release: core Redis cache, FastAPI-oriented usage, CLI, configuration, baseline documentation.

[Unreleased]: https://github.com/sirstig/yokedcache/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/sirstig/yokedcache/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/sirstig/yokedcache/compare/v0.2.4...v0.3.0
[0.2.4]: https://github.com/sirstig/yokedcache/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/sirstig/yokedcache/compare/v0.2.1...v0.2.3
[0.2.1]: https://github.com/sirstig/yokedcache/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/sirstig/yokedcache/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/sirstig/yokedcache/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/sirstig/yokedcache/compare/v0.1.0...v0.1.2
[0.1.0]: https://github.com/sirstig/yokedcache/releases/tag/v0.1.0
