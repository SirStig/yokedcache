# Security

Report vulnerabilities via [GitHub Security Advisories](https://github.com/sirstig/yokedcache/security/advisories/new) or the contact on the repository homepage.

## Trust boundaries

Treat Redis and Memcached as **trusted stores**. Anyone who can write arbitrary keys can affect what your app deserializes. Use `CacheConfig.allow_legacy_insecure_deserialization=False` once legacy blobs are gone (see changelog for the envelope format introduced in 1.0.0).

## Disk backend (`diskcache`)

The `yokedcache[disk]` extra pulls in [diskcache](https://pypi.org/project/diskcache/), which persists values with **pickle** by default.

| | |
|---|---|
| **Advisory** | [GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) (CVE-2025-69872) |
| **Affected** | diskcache through 5.6.3 (current PyPI line) |
| **Patched release** | None yet—scanners will flag this until upstream ships a fix |

If an attacker can write files under the cache directory, they can supply a malicious pickle payload that leads to arbitrary code execution when your process reads it.

**What to do:**
- Skip `yokedcache[disk]` unless you specifically need filesystem-backed caching.
- Keep the cache directory writable only by the application user—no shared paths, no world-writable directories, no network mounts where untrusted users could write.
- Prefer Redis, SQLite, or memory backends when filesystem trust is uncertain.

Note: `diskcache` ships a `JSONDisk` driver that avoids pickle, but YokedCache's `DiskCacheBackend` currently uses the default pickle-backed disk. Callers who need disk without pickle should use a custom integration or a different backend for now.

## Dependency scanning

`uv.lock` keeps **filelock** on a current, patched line. **Black** and **orjson** minimum versions in `pyproject.toml` reflect published security fixes.

## Python 3.9 and yokedcache 0.3.x

YokedCache 1.x requires Python 3.10+. If you're on Python 3.9, the last 0.3 release (`pip install "yokedcache==0.3.0"`) works as a stopgap. That branch does **not** receive the security fixes in 1.x—older dependency trees may retain known issues in orjson, filelock, and dev tooling. Upgrading to Python 3.10+ and yokedcache 1.x is strongly recommended.
