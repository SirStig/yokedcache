# Security

- **Versions:** 1.x targets **Python 3.10+** (CI covers through **3.14**). On **Python 3.9**, use **`yokedcache==0.3.0`** (or `yokedcache<1`) only as a stopgap—that branch does **not** receive the same security fixes as 1.x; upgrade when you can. Details: [SECURITY.md](https://github.com/sirstig/yokedcache/blob/main/SECURITY.md) in the repo.
- Use `rediss://` and TLS-enabled Redis in production.
- Limit Redis access to your VPC/private network; avoid public endpoints.
- For multi-tenant apps, include tenant namespace in keys and enforce isolation.
- Avoid caching sensitive data unless encrypted; consider encrypt-at-rest.
- Rotate credentials; prefer ACL users per service.
- Validate untrusted input that can influence keys to prevent key scanning attacks.
