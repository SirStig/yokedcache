# Security

Report vulnerabilities via [GitHub Security Advisories](https://github.com/sirstig/yokedcache/security/advisories/new) or the contact on the repository homepage.

## Trust boundaries

- **Redis / Memcached**: Treat as trusted stores. Anyone who can write arbitrary keys can influence what your app deserializes. Use `CacheConfig.allow_legacy_insecure_deserialization=False` once legacy blobs are gone (see changelog).

## Optional disk backend (`diskcache`)

The **`yokedcache[disk]`** extra pulls in **[diskcache](https://pypi.org/project/diskcache/)** (python-diskcache). That library persists values with **pickle** by default.

| | |
| --- | --- |
| **Advisory** | [GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) (**CVE-2025-69872**) |
| **Affected** | diskcache **through 5.6.3** (current PyPI line as of this writing) |
| **Patched PyPI version** | **None** yet; automated scanners may flag the dependency until upstream ships a release |

**Threat model:** someone who can **write or replace files under the cache directory** can supply a malicious pickle payload; when your process reads that entry, that can lead to **arbitrary code execution**.

**What we recommend**

- Do **not** install the disk extra unless you need a filesystem-backed cache.
- Keep the cache directory **writable only by the application user** (no shared multi-tenant paths, no world-writable directories, careful with network mounts).
- Prefer **Redis, SQLite, or memory** backends when untrusted parties could influence the filesystem.
- At the application layer, only cache payloads you could treat as **trusted after deserialization**; JSON or msgpack at the boundary does not remove the pickle risk inside diskcache until you stop using pickle-backed storage for those keys.

**Upstream note:** diskcache also provides **`JSONDisk`** (JSON + zlib instead of pickle). **YokedCache’s `DiskCacheBackend`** currently constructs `diskcache.Cache` with the default disk (pickle). Callers who require disk without pickle need a custom integration or another backend until this project exposes a supported switch.

## Dependency scanning

The repo uses `[tool.uv] constraint-dependencies` so `uv.lock` keeps **filelock** on a current, patched line. **Black** and **orjson** minimum versions in `pyproject.toml` reflect published security fixes for dev tooling and JSON parsing.

## Python 3.9 and yokedcache 0.3.x

**yokedcache 1.x** declares `requires-python >= 3.10`. If you run **Python 3.9**, use the last 0.3 line, e.g. **`pip install "yokedcache==0.3.0"`** (or constrain `yokedcache<1`). Expect **no security backports** on 0.3.x: older dependency trees may retain known issues (e.g. **orjson** recursion limits, **filelock** TOCTOU classes, dev-only **black** CVEs in tooling). Migrating to **Python 3.10+** and **yokedcache 1.x** is strongly recommended.
