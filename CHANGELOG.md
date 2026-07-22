# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-07-22

A comprehensive audit surfaced and fixed a large batch of correctness, security,
and reliability bugs across the whole package. Most fixes narrow existing
behavior toward its documented/intended contract rather than adding new
features, but a few are behavior changes - see the callouts below.

### Security

- **`allow_legacy_insecure_deserialization` now defaults to `False`** in
  `CacheConfig` and in every backend that had its own copy of this flag
  (`RedisBackend`, `MemcachedBackend`, `DiskCacheBackend`, `SQLiteBackend`).
  Previously, any cached payload that failed JSON parsing silently fell back
  to `pickle.loads()` by default - a straightforward deserialization-RCE
  vector if the backend is reachable by anything untrusted. Opt back in
  explicitly with `allow_legacy_insecure_deserialization=True` if you have
  pre-1.1 pickle-serialized data to migrate off of.
- `HTTPCacheMiddleware` no longer reads from or writes to the cache for a
  request carrying an `Authorization` or `Cookie` header unless you supply
  `key_builder` - previously the default cache key never varied by
  principal, so one user's authenticated response could be cached and
  replayed verbatim to a different user hitting the same path. A response
  that sets `Set-Cookie` is likewise never cached.
- CLI `ping` and `export-config` now redact any password embedded in
  `redis_url` before printing/writing it, instead of leaking it in plaintext
  to stdout or an exported config file.
- Circuit breaker's `HALF_OPEN` state now actually admits only a single
  trial call; previously every concurrent caller during the trial window
  fell through the `== OPEN` check and hit the (possibly still-broken)
  backend directly, unlike a normal half-open gate.

### Fixed

- **A cached `None` value is no longer treated as a cache miss.** `get()`,
  `fetch_or_set()`, and the `@cached` decorator (both the plain miss check
  and the async double-execution path, see below) previously used `None` as
  their own "not found" sentinel, so a value your application legitimately
  cached as `None`/`null` was silently discarded and replaced with the
  caller's `default` on every read.
- **`@cached` no longer executes the wrapped async function twice on
  error.** With the default `skip_cache_on_error=True`, an exception raised
  by the wrapped function itself (not just a cache-layer failure) was
  caught by the same handler that retries on cache errors, causing the
  function - including any side effect like a charge or a write - to run a
  second time before the exception was finally raised to the caller.
- **SQLite backend (`SQLiteBackend`) no longer deadlocks on an expired-key
  read.** `get()` called `delete()` internally while still holding its own
  (non-reentrant) `asyncio.Lock`, hanging that call forever and, since the
  lock was never released, every subsequent call on the same backend
  instance too. Also: values are now actually serialized (previously a
  `dict`/`list` value raised `sqlite3.InterfaceError`), `exists()` and
  `get_all_keys()` now honor TTL (previously an expired key still reported
  as existing), `expire()` now returns `False` for a nonexistent key instead
  of always `True`, and tag-based invalidation is now implemented instead
  of silently being a no-op.
- **Disk backend (`DiskCacheBackend`) tag invalidation is now implemented**
  instead of silently doing nothing, and `connect()` is now idempotent
  (calling it twice no longer leaks a file handle from the first open).
- **Redis backend tag-set TTL is no longer clobbered downward.** Adding a
  short-lived key to a tag already used by a longer-lived key used to reset
  the whole tag set's expiry to the new key's (shorter) TTL, so the tag set
  could expire out from under the still-live key and `invalidate_tags()`
  would silently stop finding it.
- **Memcached backend now actually uses every configured server** instead
  of silently talking to only the first one; keys are sharded across
  servers by a stable checksum so the same key always maps to the same
  server across restarts and worker processes.
- Naive vs. timezone-aware `datetime` mismatch fixed: `CacheEntry.is_expired`
  and `.age_seconds` used `datetime.utcnow()` while `cache.py`,
  `vector_search.py`, and `memory.py` constructed entries with tz-aware
  timestamps, raising `TypeError` on the very first comparison. Backend
  `fuzzy_search()` call sites that built naive timestamps were also updated
  for consistency.
- `generate_cache_key(..., user_id=0)` no longer collides with the
  unscoped/no-user key - `user_id` was checked with `if user_id:`, and `0`
  (a common first auto-increment user id) is falsy in Python.
- Stale-if-error no longer masks ordinary cache misses/expirations. The
  check used to run on `get()`'s success path, so it couldn't tell "the
  backend errored" from "the key simply doesn't exist any more" and served
  stale data past a key's real TTL with zero backend errors involved. It
  now only triggers from the exception path, on a genuine backend failure.
- `HTTPCacheMiddleware` now replays the original response's headers (e.g.
  `Content-Type`) on a cache hit instead of only `ETag`/`Cache-Control`, and
  includes the query string in its cache key by default (`include_query`
  now defaults to `True`) so `/search?q=cats` and `/search?q=dogs` no longer
  collide on the same cache entry. Also fixed a pre-existing bug where a
  response body cached under the default JSON serialization was silently
  corrupted (stored as the Python `repr()` of the bytes rather than the
  bytes themselves), which meant a cache hit could never actually replay
  correctly.
- `cache.py`'s `_InflightLockMap` (single-flight/stampede-protection locks)
  no longer evicts a lock that's currently held; the previous LRU eviction
  could silently mint a second, unlocked lock for a key whose load was
  still in progress, letting a concurrent caller stampede past it.
- `cache.py`'s `_stale_store` is now bounded and pruned on a confirmed clean
  miss, instead of only ever shrinking via explicit `delete`/`invalidate`/
  `flush_all` calls - a long-running, high-key-cardinality, TTL-based
  workload could grow it indefinitely.
- `cache.py`'s `exists()` now checks the sanitized (prefixed) key first,
  matching `delete()`'s priority - previously it checked the raw key first,
  the opposite order, which could disagree with `get()` about whether a key
  "exists" if an unrelated same-named key happened to exist in a shared
  Redis DB.
- `cache.py.disconnect()` and `RedisBackend.disconnect()` now always clear
  the connected flag even if closing the underlying client raises;
  previously a raise during teardown left the instance believing it was
  still connected, making a subsequent `connect()` a silent no-op.
- SWR (`SWRScheduler`) no longer loses track of the newly-scheduled task on
  a successful refresh. The reschedule call happened synchronously inside
  the finishing task, which then unconditionally popped whatever task was
  now registered under that key - i.e. the *new* task's entry, not its own -
  orphaning it from `get_active_refreshes()`/`get_stats()`/`stop()`. The
  retry-after-failure path is now tracked in `_refresh_tasks` too, for the
  same reason.
- `initialize_tracing(sample_rate=...)` no longer replaces an
  already-configured `TracerProvider` (and thus silently drops all of its
  span processors/exporters); it only installs a sampled provider when none
  has been explicitly configured yet.
- `CacheMetrics` no longer double-counts a single failed operation under
  both its operation-type and its exception-type key, which previously
  could push `get_error_rate()` above 100%. Per-table and per-tag
  `avg_response_time` are now actually computed instead of always
  reporting `0.0` (both previously read from a dict key nothing ever wrote
  to).
- CLI: `--redis-url`/`YOKEDCACHE_REDIS_URL` no longer silently overrides a
  `redis_url` loaded from `--config`; the flag had a non-empty default, so
  it always looked "explicitly passed" and clobbered the config file's
  value on every run regardless of whether the user actually passed `-r`.
- CLI: `export-config` no longer crashes when any table has tags. The `list`
  and `set` subcommands were defined as module-level functions named `list`
  and `set`, which shadowed the builtins package-wide; `export-config`'s use
  of the real `list()` builtin was calling the shadowed Click command
  instead and crashing. Both subcommands keep their CLI-visible names
  (`yokedcache list`, `yokedcache set`) via explicit `@main.command("...")`.
- CLI: `flush`'s confirmation prompt now describes the same target it's
  about to act on. If more than one of `--key`/`--pattern`/`--tags` was
  passed at once, the prompt and the actual delete used opposite priority
  orders, so confirming could authorize a different action than the one
  that ran.
- Config env-var overrides no longer silently store a `str` into an
  `Optional[int]`/`Optional[float]` field (e.g. `YOKEDCACHE_REDIS_PORT`)
  when that field's current value is `None` - the type-coercion check only
  looked at the field's runtime value, which can't distinguish "unset" from
  "meant to be a string," and now falls back to the field's declared type
  annotation in that case.

### Changed

- `HTTPCacheMiddleware`'s `include_query` default changed from `False` to
  `True` (see Fixed, above) - if you rely on the old default, pass
  `include_query=False` explicitly.

### Known limitations (not changed in this release)

- `MemcachedBackend` tag membership is still tracked in this process's
  memory only (not persisted in Memcached itself), so it doesn't survive a
  process restart and isn't shared across worker processes. A fully
  correct fix needs an atomic, Memcached-native index (CAS-based
  read-modify-write), which was out of scope for this pass.
- `cached_dependency()`'s non-generator wrapper still always re-invokes the
  wrapped dependency rather than serving a cached result on a hit. Its
  primary documented use case is DB session factories (e.g. `get_db()`),
  where actually reusing a cached session object across requests would be
  its own hazard; making the "plain value" case behave differently first
  needs a reliable way to tell the two apart, which the current signature
  doesn't provide.
- Config env-var overrides still can't distinguish "explicitly passed a
  value equal to the field's own default" from "not passed at all" - both
  cases look identical after `__init__` runs, so an env var can still win
  over an explicit constructor argument in that specific case.

## [1.0.3] - 2026-07-22

### Security

- Regenerated `uv.lock` (`uv lock --upgrade`). A `pip-audit` pass against the previous lock found 15 known vulnerabilities across 6 packages; after the upgrade only one remains, and it's a documented non-issue for this project (see below). Notable fixes pulled in:
  - **cryptography** 46.0.7 → 49.0.0 ([GHSA-537c-gmf6-5ccf](https://github.com/advisories/GHSA-537c-gmf6-5ccf), statically linked OpenSSL advisory in wheels before 48.0.1).
  - **click** 8.3.2 → 8.4.2 (PYSEC-2026-2132, command injection via `click.edit()`).
  - **urllib3** 2.6.3 → 2.7.0 (PYSEC-2026-142, PYSEC-2026-141 — decompression resource exhaustion and cross-origin header leakage).
  - **idna** 3.11 → 3.18 (PYSEC-2026-215, incomplete fix for the `idna.encode()` DoS originally tracked as CVE-2024-3651).
  - **starlette** 1.0.0 → 1.3.1 (`web` extra; PYSEC-2026-161/248/249/2280/2281 — Host-header/path URL-reconstruction bypasses, unbounded `application/x-www-form-urlencoded` parsing, Windows UNC-path SSRF via `StaticFiles`, and unrestricted `HTTPEndpoint` method dispatch).
- `[tool.uv] constraint-dependencies` now also floors **click** (≥8.3.3), **urllib3** (≥2.7.0), **idna** (≥3.15), and **starlette** (≥1.3.1), and raises the existing **cryptography** floor to ≥48.0.1, so a future `uv lock` (without `--upgrade`) can't silently drift back to a pre-fix release.
- `redis` optional-dependency floor raised **≥4.0.0 → ≥5.0.0**: the test suite only validates against redis-py 8.0.1, and 5.0+ is what actually guarantees an async `aclose()` (see Fixed, below).
- Remaining `pip-audit` finding — **diskcache** 5.6.3, PYSEC-2026-2447 (pickle-by-default deserialization) — has no upstream fix version yet and is unchanged from 1.0.2: `DiskCacheBackend` already avoids pickle for application cache values via `diskcache.JSONDisk` (see `SECURITY.md`).

### Fixed

- `RedisBackend.set()` now issues `SET key value EX ttl` instead of the deprecated pipelined `SETEX` call (redis-py 8.0 flags `setex()` for eventual removal in favor of `set(..., ex=...)`).
- `RedisBackend.disconnect()` now prefers `aclose()` over the deprecated `close()` when available, matching the guard `YokedCache.close()` already used.

### Changed

- `[tool.mypy] python_version` raised `3.10` → `3.12`. This only controls which syntax mypy accepts while type-checking (numpy's stub now uses a PEP 695 `type` statement that requires it); the package's actual supported Python range (`>=3.10`, per `requires-python`) is unchanged.

## [1.0.2] - 2026-04-15

### Security

- `[tool.uv] constraint-dependencies` pins **cryptography** ≥46.0.7, **pygments** ≥2.20.0, and **requests** ≥2.33.0 so `uv.lock` resolves to releases that address CVE-2026-34073 / CVE-2026-39892, CVE-2026-4539, and CVE-2026-25645 respectively (per `pip-audit` at lock refresh time).
- **Dev** optional dependency **pytest** raised to **≥9.0.3** (CVE-2025-71176). Regenerated `uv.lock`.
- **Disk backend:** `DiskCacheBackend` now uses **diskcache.JSONDisk** and stores JSON-safe wrappers around **bytes** from `serialize_for_cache` / `deserialize_from_cache`, avoiding pickle for application cache values on disk. **Remove or move the cache directory** when upgrading from pre-1.0.2 disk data (old pickle-backed entries are not read). Automated scanners may still flag the **diskcache** package until upstream publishes a patched release.

### Documentation

- `SECURITY.md`, README, and docs site *Security* updated for JSONDisk behavior, directory trust boundaries, and the diskcache advisory ([GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)).

## [1.0.1] - 2026-03-26

Slimmer default install and clearer optional extras. Behavior for a **Redis server** is unchanged once you install the `redis` extra (or `full`).

### Changed

- **Core dependencies** are now `orjson`, `pyyaml`, `click`, and `typing-extensions` only. **`redis`** and **`fastapi`** are no longer installed by a plain `pip install yokedcache`.
- Without `redis`, `YokedCache.connect()` uses an **in-process memory** store so the same async API works for local scripts and tests without Redis.
- **`HTTPCacheMiddleware`** depends on **Starlette** only; install `yokedcache[web]` (or `full`). Docstrings use Starlette as the primary example.
- New grouped extras in metadata: **`redis`**, **`web`**, **`backends`** (disk + sqlite + memcached), **`observability`** (monitoring + tracing). Granular extras (`memcached`, `disk`, `sqlite`, `monitoring`, `tracing`, etc.) are unchanged. **`full`** still pulls the former “batteries included” set, including `redis` and `fastapi`.

### Fixed

- Misleading `ImportError` in `yokedcache.__init__` that always blamed Redis when `YokedCache` failed to import.

### Upgrade note (read this if you upgrade from 1.0.0)

If your project relied on **transitive** `redis` or `fastapi` from `pip install yokedcache` without listing them in your own requirements, add explicit dependencies or install:

`pip install "yokedcache[redis]"` for Redis, `pip install "yokedcache[web]"` for HTTP middleware, or `pip install "yokedcache[full]"` to approximate the old default footprint.

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

[Unreleased]: https://github.com/sirstig/yokedcache/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/sirstig/yokedcache/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/sirstig/yokedcache/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/sirstig/yokedcache/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/sirstig/yokedcache/compare/v0.2.4...v0.3.0
[0.2.4]: https://github.com/sirstig/yokedcache/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/sirstig/yokedcache/compare/v0.2.1...v0.2.3
[0.2.1]: https://github.com/sirstig/yokedcache/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/sirstig/yokedcache/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/sirstig/yokedcache/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/sirstig/yokedcache/compare/v0.1.0...v0.1.2
[0.1.0]: https://github.com/sirstig/yokedcache/releases/tag/v0.1.0
