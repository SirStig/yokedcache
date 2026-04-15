# Security

---

## Python version support

YokedCache 1.x requires **Python 3.10+** (CI covers 3.10–3.14). On Python 3.9, use `yokedcache==0.3.0` as a stopgap—that branch doesn't receive the security fixes in 1.x. Upgrade when you can.

---

## Trust boundaries

**Redis and Memcached are trusted stores.** Anyone who can write arbitrary keys can affect what your app deserializes. Protect them accordingly:

- Keep Redis in a private network—never expose port 6379 to the internet
- Use authentication (Redis `requirepass` or ACL)
- Use TLS (`rediss://`) for any connection that crosses network boundaries

**The deserialization envelope (1.x):**

YokedCache 1.0.0 introduced a typed envelope format. Once you've migrated away from 0.x entries, set:

```python
config = CacheConfig(allow_legacy_insecure_deserialization=False)
```

This rejects any entry not written with the 1.x envelope, preventing a class of injection attacks where an attacker writes a raw pickle or JSON blob as a cache value.

---

## Disk backend (diskcache)

The `yokedcache[disk]` extra uses [diskcache](https://pypi.org/project/diskcache/). **From yokedcache 1.0.2**, `DiskCacheBackend` uses **JSONDisk** and stores only JSON-safe wrappers around **bytes** from the same envelope helpers as Redis—application cache values are **not** persisted with pickle on that path. **Clear the cache directory** when upgrading from pre-1.0.2 disk data.

| | |
|---|---|
| **Advisory** | [GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) (CVE-2025-69872) |
| **Upstream package** | diskcache ≤ 5.6.3 (current PyPI); **no patched wheel** yet—scanners may still flag the dependency. |
| **YokedCache** | Disk backend avoids pickle for stored cache payloads as above; the cache directory remains a **trust boundary** (SQLite metadata and files). |

**Mitigations:**
- Skip `yokedcache[disk]` if you don't need filesystem-backed caching—Redis or SQLite are alternatives
- Keep the cache directory writable only by the application user: `chmod 700 /var/cache/myapp`
- Never use shared or network-mounted paths where untrusted users can write
- Avoid the disk backend in multi-tenant environments when filesystem trust is unclear

---

## Pickle serialization

Pickle deserializes arbitrary Python objects and **can execute code on load**. Rules:

1. Only pickle data that came from your own application
2. Never pickle data from user input
3. Only use pickle with backends you fully control (private Redis, local memory)
4. Prefer JSON or MessagePack for data that touches external systems

---

## HTTP middleware security

`HTTPCacheMiddleware` caches full HTTP responses. Without a custom `key_builder`, the default key is the URL only—two different users hitting the same URL will share a response:

```python
# UNSAFE for authenticated routes:
app.add_middleware(HTTPCacheMiddleware, cache=cache, ttl=60)

# SAFE: vary key by user
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,
    key_builder=lambda req: f"{req.url}:{req.headers.get('x-user-id', 'anon')}",
    exclude_paths=["/admin", "/account", "/billing"],
)
```

Never cache responses that contain user-specific data without a per-user key.

---

## Multi-tenant isolation

In multi-tenant apps, ensure tenants can't see each other's data:

```python
# Option 1: per-tenant key prefix
config = CacheConfig(key_prefix=f"tenant_{tenant_id}")

# Option 2: include tenant in all keys manually
await cache.set(f"tenant:{tenant_id}:user:{user_id}", data)

# Option 3: per-tenant backend with per-prefix routing
config = CacheConfig(
    prefix_backends={
        f"tenant_{tenant_id}": RedisBackend(redis_url=...),
    }
)
```

---

## Input validation

If user input influences cache keys, validate or sanitize it to prevent key scanning attacks:

```python
import re

def safe_key(user_input: str) -> str:
    # Allow only alphanumeric + common separators
    return re.sub(r"[^a-zA-Z0-9:_\-]", "", user_input)[:128]

key = f"search:{safe_key(request.query_params.get('q', ''))}"
```

---

## Sensitive data

Avoid caching data that shouldn't be at rest in Redis:

- Passwords, credentials, private keys → **never cache**
- Payment card numbers → **never cache**
- PII (emails, phone numbers) → **encrypt before caching or avoid**
- Session tokens → **cache with short TTL; vary key by user**

If you must cache sensitive data, encrypt it at the application layer before calling `cache.set()`.

---

## Production security checklist

- [ ] Redis not exposed to the internet (VPC/private network only)
- [ ] `rediss://` (TLS) for any Redis not on localhost
- [ ] Redis ACL user with least-privilege permissions
- [ ] Credentials in secrets manager / env vars, not source code
- [ ] `allow_legacy_insecure_deserialization=False` (after migrating from 0.x)
- [ ] `HTTPCacheMiddleware` key builder varies by user on authenticated routes
- [ ] Disk extra not installed if not needed; cache dir non-world-writable if used
- [ ] Pickle serialization only used with trusted backends
- [ ] User input sanitized before use in cache keys

---

## Reporting vulnerabilities

Report via [GitHub Security Advisories](https://github.com/sirstig/yokedcache/security/advisories/new)—not public issues. See [SECURITY.md](https://github.com/sirstig/yokedcache/blob/main/SECURITY.md) in the repository for the full write-up on trust boundaries and known third-party advisories.
