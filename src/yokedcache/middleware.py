"""HTTP caching middleware (Starlette ASGI) providing ETag & Cache-Control support.

Requires the ``web`` extra: ``pip install "yokedcache[web]"`` (installs Starlette).

Usage:
    from starlette.applications import Starlette
    from yokedcache.middleware import HTTPCacheMiddleware
    from yokedcache.cache import YokedCache

    cache = YokedCache()
    app = Starlette()
    app.add_middleware(HTTPCacheMiddleware, cache=cache, default_ttl=60)

Notes:
    - Only caches 200 OK JSON/text responses by default.
    - Uses MD5 hash of body as ETag; weak etags (W/) can be enabled later.
    - Honors If-None-Match header and returns 304 when etag matches.
    - Cache key pattern: http:{method}:{path}?{query_string} - the query
      string is included by default (pass include_query=False to opt out),
      since two requests to the same path with different query strings are
      generally different resources.
    - Security: a request carrying an Authorization or Cookie header is
      passed straight through (never read from or written to the cache)
      unless you supply key_builder, since this middleware has no way to
      know how to vary the key per principal on its own. A response that
      sets Set-Cookie is likewise never cached. If you do supply
      key_builder, make sure it varies the key per principal yourself -
      that opts back into caching authenticated/cookied requests.

# flake8: noqa
"""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Any, Callable, Optional

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

if TYPE_CHECKING:
    _ScopeKeyBuilder = Callable[[Scope], str]
else:
    _ScopeKeyBuilder = Any


class HTTPCacheMiddleware:  # pragma: no cover - integration layer
    def __init__(
        self,
        app: ASGIApp,
        cache: Any,
        default_ttl: int = 60,
        include_query: bool = True,
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

        headers = Headers(scope=scope)
        client_etag = headers.get("if-none-match")

        # Never read from or write to the cache for a request carrying
        # credentials unless the caller supplied a key_builder - without
        # one, every principal hitting this path would collide on the same
        # cache key and one user's response would be served to another.
        has_credentials = bool(headers.get("authorization") or headers.get("cookie"))
        if has_credentials and self._key_builder is None:
            await self.app(scope, receive, send)
            return

        cache_key = self._build_key(scope)

        cached = await self.cache.get(cache_key, default=None)
        if cached is not None and isinstance(cached, dict):
            # Body is stored base64-encoded (see below) since a raw `bytes`
            # value silently corrupts under the default JSON serialization -
            # orjson has no bytes support, so it falls back to str(bytes_obj)
            # and stores the *repr* of the bytes rather than the bytes
            # themselves, breaking every cache hit under default config.
            raw_body = cached.get("body", "")
            body_bytes = (
                base64.b64decode(raw_body) if isinstance(raw_body, str) else raw_body
            )
            etag = cached.get("etag")
            cached_headers = cached.get("headers") or []
            if client_etag and etag and self._etag_matches(client_etag, etag):
                # Return 304
                etag_value: str = etag

                async def send_304(message):
                    if message["type"] == "http.response.start":
                        headers_list = [(b"etag", etag_value.encode())]
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

            # Serve cached response, replaying the originally captured
            # headers (e.g. Content-Type) rather than only etag/cache-control.
            async def send_cached(message):
                if message["type"] == "http.response.start":
                    replay = [
                        (k.encode("latin-1"), v.encode("latin-1"))
                        for k, v in cached_headers
                        if k.lower() not in ("etag", "cache-control")
                    ]
                    replay.append((b"etag", etag.encode() if etag else b""))
                    replay.append((b"cache-control", self.cache_control.encode()))
                    message["headers"].extend(replay)
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
        captured_headers: list = []

        async def capture_send(message):
            if message["type"] == "http.response.start":
                status_code_holder["status"] = message.get("status", 200)
                captured_headers.clear()
                for k, v in message.get("headers", []):
                    captured_headers.append((k.decode("latin-1"), v.decode("latin-1")))
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    chunks.append(body)
            await send(message)

        await self.app(scope, receive, capture_send)

        status = status_code_holder["status"]
        if status != 200:  # only cache 200
            return
        # A response that sets cookies is establishing/refreshing
        # session/personalized state - caching it would replay that same
        # Set-Cookie (and whatever body it's paired with) to every other
        # caller of this path.
        if any(k.lower() == "set-cookie" for k, _ in captured_headers):
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
            {
                "etag": etag,
                "body": base64.b64encode(body_bytes).decode("ascii"),
                "status": status,
                "headers": captured_headers,
            },
            ttl=self.default_ttl,
        )
        # Note: Original response already sent. Cannot modify headers post-hoc without full buffering; advanced variant could intercept fully.
