# HTTP Cache Middleware

YokedCache ships a Starlette middleware that adds HTTP-level caching: `ETag`, `Cache-Control`, and `If-None-Match` support. Works with FastAPI, Starlette, and any ASGI framework.

```bash
pip install "yokedcache[web]"
```

---

## How it works

On each request:

1. Build a cache key from the request (URL by default, customizable)
2. Check the cache for a stored response
3. **Hit:** Return the cached response. If the request includes `If-None-Match` and the ETag matches, return `304 Not Modified`
4. **Miss:** Let the request pass through, cache the response, add `ETag` and `Cache-Control` headers

---

## Basic setup

```python
from fastapi import FastAPI
from yokedcache import YokedCache
from yokedcache.config import CacheConfig
from yokedcache.middleware import HTTPCacheMiddleware

cache = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))
app = FastAPI()

app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,  # seconds
)
```

> **Important:** Don't use this middleware on authenticated routes without a custom `key_builder`. The default key is the URL only—two different users hitting the same URL will share a cache entry and may see each other's data.

---

## Custom key builder

The `key_builder` callable receives the request and returns a string cache key. Use it to vary the cache by user, tenant, or any other dimension:

```python
# Vary by authenticated user
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,
    key_builder=lambda req: f"{req.url}:{req.headers.get('x-user-id', 'anon')}",
)

# Vary by tenant
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,
    key_builder=lambda req: f"{req.url}:{req.headers.get('x-tenant-id', 'default')}",
)

# Vary by URL + query string + accept header
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,
    key_builder=lambda req: f"{req.url}:{req.headers.get('accept', '')}",
)

# Custom async key builder
async def build_key(request):
    token = request.headers.get("authorization", "")
    user_id = await resolve_token(token)
    return f"{request.url}:{user_id}"

app.add_middleware(HTTPCacheMiddleware, cache=cache, ttl=60, key_builder=build_key)
```

---

## Selective caching with `cache_control`

Skip caching for certain routes or conditions:

```python
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,
    # Only cache GET and HEAD requests
    methods=["GET", "HEAD"],
    # Don't cache if the response has a non-200 status
    cache_non_ok=False,
    # Skip routes matching these prefixes
    exclude_paths=["/admin", "/health", "/metrics"],
)
```

---

## ETag and conditional requests

The middleware automatically:

- Generates an `ETag` from the response body hash
- Returns the `ETag` in response headers
- Handles `If-None-Match` headers on subsequent requests—returns `304 Not Modified` instead of the full body when the ETag matches

```
Client                        Server
  │                              │
  ├──GET /products───────────────▶│
  │◀──200 OK + ETag: "abc123"────┤
  │                              │
  ├──GET /products               │
  │  If-None-Match: "abc123"─────▶│
  │◀──304 Not Modified───────────┤ (no body, much faster)
```

---

## Cache-Control headers

The middleware sets `Cache-Control: max-age={ttl}` on cached responses. Browsers and CDNs can use this for client-side or edge caching.

```python
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=300,
    # Add "public" to allow CDN caching
    cache_control_extra="public",
    # Or "private" for authenticated responses
    # cache_control_extra="private",
)
```

---

## Invalidating HTTP cached responses

HTTP responses are stored with tags you specify. Invalidate them the same way as any other cache entry:

```python
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=60,
    tags=["http_responses", "products"],
)

# After a product update, invalidate HTTP responses too
await cache.invalidate_tags(["products"])
```

---

## Middleware options reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cache` | `YokedCache` | required | The cache instance |
| `ttl` | `int` | `60` | Response TTL in seconds |
| `key_builder` | `Callable` | URL-based | Function to build the cache key from a request |
| `methods` | `list[str]` | `["GET", "HEAD"]` | HTTP methods to cache |
| `exclude_paths` | `list[str]` | `[]` | Path prefixes to skip |
| `cache_non_ok` | `bool` | `False` | Whether to cache non-200 responses |
| `tags` | `list[str]` | `[]` | Tags to attach to all cached responses |
| `cache_control_extra` | `str \| None` | `None` | Extra Cache-Control directive (`"public"`, `"private"`) |

---

## Full FastAPI example

```python
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from yokedcache import YokedCache
from yokedcache.config import CacheConfig
from yokedcache.middleware import HTTPCacheMiddleware

cache = YokedCache(CacheConfig(redis_url="redis://localhost:6379/0"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    yield
    await cache.disconnect()

app = FastAPI(lifespan=lifespan)

# Public API: cache by URL + Accept header
app.add_middleware(
    HTTPCacheMiddleware,
    cache=cache,
    ttl=300,
    tags=["api_responses"],
    key_builder=lambda req: f"{req.url}:{req.headers.get('accept', '')}",
    exclude_paths=["/auth", "/admin", "/health"],
    cache_control_extra="public",
)

@app.get("/products")
async def list_products():
    return await fetch_products()

@app.get("/products/{product_id}")
async def get_product(product_id: str):
    return await fetch_product(product_id)

@app.post("/products/{product_id}")
async def update_product(product_id: str, data: dict):
    await save_product(product_id, data)
    # Invalidate both the server-side cache and HTTP response cache
    await cache.invalidate_tags(["api_responses", "products"])
    return {"ok": True}
```
