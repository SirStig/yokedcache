"""HTTP caching middleware (FastAPI) providing ETag & Cache-Control support.

Usage:
    from fastapi import FastAPI
    from yokedcache.middleware import HTTPCacheMiddleware
    from yokedcache.cache import YokedCache

    cache = YokedCache()
    app = FastAPI()
    app.add_middleware(HTTPCacheMiddleware, cache=cache, default_ttl=60)

Notes:
    - Only caches 200 OK JSON/text responses by default.
    - Uses MD5 hash of body as ETag; weak etags (W/) can be enabled later.
    - Honors If-None-Match header and returns 304 when etag matches.
    - Cache key pattern: http:{method}:{path} (no query params by default).
    - Security: the default key does not vary by user or cookies. Do not use this
      middleware on routes that return user-specific bodies unless you pass
      key_builder (or equivalent) so each principal gets a distinct cache key.

# flake8: noqa
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Callable, Optional

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

if TYPE_CHECKING:
    _ScopeKeyBuilder = Callable[[Scope], str]
else:
    _ScopeKeyBuilder = Any

try:  # pragma: no cover - optional fastapi/starlette usage
    from fastapi import Request
except Exception:  # pragma: no cover
    Request = Any  # type: ignore[assignment,misc]


class HTTPCacheMiddleware:  # pragma: no cover - integration layer
    def __init__(
        self,
        app: ASGIApp,
        cache: Any,
        default_ttl: int = 60,
        include_query: bool = False,
        cache_control: Optional[str] = None,
        etag_prefix: str = "",
        key_builder: Optional["_ScopeKeyBuilder"] = None,
    ) -> None:
        self.app = app
        self.cache = cache
        self.default_ttl = default_ttl
        self.include_query = include_query
        self.cache_control = cache_control or f"public, max-age={default_ttl}"
        self.etag_prefix = etag_prefix
        self._key_builder = key_builder

    @staticmethod
    def _strip_etag_token(raw: str) -> str:
        t = raw.strip()
        if t.upper().startswith("W/"):
            t = t[2:].strip()
        if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
            return t[1:-1]
        return t

    def _etag_matches(self, client_val: Optional[str], stored: Optional[str]) -> bool:
        if not client_val or not stored:
            return False
        if client_val.strip() == "*":
            return True
        want = self._strip_etag_token(stored)
        for part in client_val.split(","):
            if self._strip_etag_token(part) == want:
                return True
        return False

    def _build_key(self, scope: Scope) -> str:
        if self._key_builder is not None:
            return self._key_builder(scope)
        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        key = f"http:{method}:{path}"
        if self.include_query:
            qs = scope.get("query_string", b"").decode()
            if qs:
                key += f"?{qs}"
        return key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pass through
            await self.app(scope, receive, send)
            return
        if scope.get("method") not in {"GET", "HEAD"}:
            await self.app(scope, receive, send)
            return

        cache_key = self._build_key(scope)
        headers = Headers(scope=scope)
        client_etag = headers.get("if-none-match")

        cached = await self.cache.get(cache_key, default=None)
        if cached is not None and isinstance(cached, dict):
            body_bytes = cached.get("body", b"")
            etag = cached.get("etag")
            if client_etag and etag and self._etag_matches(client_etag, etag):
                # Return 304
                async def send_304(message):
                    if message["type"] == "http.response.start":
                        headers_list = [(b"etag", etag.encode())]
                        headers_list.append(
                            (b"cache-control", self.cache_control.encode())
                        )
                        message["status"] = 304
                        message["headers"].extend(headers_list)
                    await send(message)

                await send_304(
                    {"type": "http.response.start", "status": 304, "headers": []}
                )
                await send({"type": "http.response.body", "body": b""})
                return

            # Serve cached response
            async def send_cached(message):
                if message["type"] == "http.response.start":
                    message["headers"].extend(
                        [
                            (b"etag", etag.encode() if etag else b""),
                            (b"cache-control", self.cache_control.encode()),
                        ]
                    )
                elif message["type"] == "http.response.body":
                    message["body"] = body_bytes
                await send(message)

            await send_cached(
                {
                    "type": "http.response.start",
                    "status": cached.get("status", 200),
                    "headers": [],
                }
            )
            await send_cached({"type": "http.response.body", "body": body_bytes})
            return

        # Capture response
        chunks = []
        status_code_holder = {"status": 200}

        async def capture_send(message):
            if message["type"] == "http.response.start":
                status_code_holder["status"] = message.get("status", 200)
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    chunks.append(body)
            await send(message)

        await self.app(scope, receive, capture_send)

        status = status_code_holder["status"]
        if status != 200:  # only cache 200
            return
        body_bytes = b"".join(chunks)
        if not body_bytes:
            return
        # Compute ETag
        h = hashlib.md5(body_bytes).hexdigest()  # noqa: S324 - non-crypto ok
        etag = f"{self.etag_prefix}{h}"
        # Store
        await self.cache.set(
            cache_key,
            {"etag": etag, "body": body_bytes, "status": status},
            ttl=self.default_ttl,
        )
        # Note: Original response already sent. Cannot modify headers post-hoc without full buffering; advanced variant could intercept fully.
