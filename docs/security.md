# Security

- Use `rediss://` and TLS-enabled Redis in production.
- Limit Redis access to your VPC/private network; avoid public endpoints.
- For multi-tenant apps, include tenant namespace in keys and enforce isolation.
- Avoid caching sensitive data unless encrypted; consider encrypt-at-rest.
- Rotate credentials; prefer ACL users per service.
- Validate untrusted input that can influence keys to prevent key scanning attacks.
