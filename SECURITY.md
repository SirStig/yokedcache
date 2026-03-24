# Security

Report vulnerabilities via [GitHub Security Advisories](https://github.com/sirstig/yokedcache/security/advisories/new) or the contact on the repository homepage.

## Trust boundaries

- **Redis / Memcached**: Treat as trusted stores. Anyone who can write arbitrary keys can influence what your app deserializes. Use `CacheConfig.allow_legacy_insecure_deserialization=False` once legacy blobs are gone (see changelog).
- **Disk backend (`yokedcache[disk]`)**: The optional `diskcache` library persists values with **pickle** by default. There is **no patched diskcache release** yet for [CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) (unsafe pickle deserialization if an attacker can write the cache directory). Only use the disk extra when the cache directory is **not writable by untrusted users**; prefer JSON/msgpack serialization at the application layer where feasible.

## Dependency scanning

The repo uses `[tool.uv] constraint-dependencies` so `uv.lock` keeps **filelock** on a current, patched line. **Black** and **orjson** minimum versions in `pyproject.toml` reflect published security fixes for dev tooling and JSON parsing.

## Python 3.9 and yokedcache 0.3.x

**yokedcache 1.x** declares `requires-python >= 3.10`. If you run **Python 3.9**, use the last 0.3 line, e.g. **`pip install "yokedcache==0.3.0"`** (or constrain `yokedcache<1`). Expect **no security backports** on 0.3.x: older dependency trees may retain known issues (e.g. **orjson** recursion limits, **filelock** TOCTOU classes, dev-only **black** CVEs in tooling). Migrating to **Python 3.10+** and **yokedcache 1.x** is strongly recommended.
