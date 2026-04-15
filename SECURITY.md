# Security

Report vulnerabilities via [GitHub Security Advisories](https://github.com/sirstig/yokedcache/security/advisories/new) or the contact on the repository homepage.

## Trust boundaries

Treat Redis and Memcached as **trusted stores**. Anyone who can write arbitrary keys can affect what your app deserializes. Use `CacheConfig.allow_legacy_insecure_deserialization=False` once legacy blobs are gone (see changelog for the envelope format introduced in 1.0.0).

## Disk backend (`diskcache`)

The `yokedcache[disk]` extra pulls in [diskcache](https://pypi.org/project/diskcache/). **From yokedcache 1.0.2**, `DiskCacheBackend` uses **diskcache.JSONDisk** and stores only JSON-safe wrappers around **bytes** produced by `serialize_for_cache` / read by `deserialize_from_cache`, so application cache values are not persisted via pickle on that path.

| | |
|---|---|
| **Advisory** | [GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) (CVE-2025-69872) |
| **Upstream package** | diskcache through 5.6.3 (current PyPI line); **no patched wheel** yet—automated scanners may still flag the dependency. |
| **YokedCache behavior** | Disk backend avoids pickle for stored cache payloads as above. **Upgrade note:** on-disk data from **before 1.0.2** used the default pickle-backed layout and is **not compatible**—remove or move the cache directory when upgrading. |

If an attacker can still write or replace files under the cache directory (including SQLite metadata used by diskcache), treat the directory as a **trust boundary**—use strict permissions and avoid shared volumes with untrusted writers.

**What to do:**
- Skip `yokedcache[disk]` unless you specifically need filesystem-backed caching.
- Keep the cache directory writable only by the application user—no shared paths, no world-writable directories, no network mounts where untrusted users could write.
- Prefer Redis, SQLite, or memory backends when filesystem trust is uncertain.

## Dependency scanning

The repo uses `[tool.uv] constraint-dependencies` so `uv.lock` keeps **filelock**, **cryptography**, **pygments**, and **requests** on current, patched lines where advisories apply. **Black**, **orjson**, and **pytest** (dev) minimum versions in `pyproject.toml` reflect published security fixes for dev tooling, JSON parsing, and tests.

## Python 3.9 and yokedcache 0.3.x

YokedCache 1.x requires Python 3.10+. If you're on Python 3.9, the last 0.3 release (`pip install "yokedcache==0.3.0"`) works as a stopgap. That branch does **not** receive the security fixes in 1.x—older dependency trees may retain known issues in orjson, filelock, and dev tooling. Upgrading to Python 3.10+ and yokedcache 1.x is strongly recommended.
