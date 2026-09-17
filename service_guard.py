"""Small, process-local request protections for a single ASGI worker."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import json
import logging
import math
import os
import re
import time
from uuid import uuid4


ACCESS_LOG = logging.getLogger("healthquery.access")
SECURITY_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"referrer-policy": b"no-referrer",
    b"content-security-policy": (
        b"default-src 'self'; style-src 'self'; script-src 'self'; "
        b"connect-src 'self'; img-src 'self' data:; object-src 'none'; "
        b"base-uri 'none'; frame-ancestors 'self' https://huggingface.co; form-action 'self'"
    ),
}


@dataclass(frozen=True)
class Settings:
    body_limit_bytes: int = 8192
    rate_limit: int = 60
    rate_window_seconds: int = 60
    max_inflight: int = 4

    @classmethod
    def from_env(cls):
        limits = {
            "body_limit_bytes": (8192, 1_048_576),
            "rate_limit": (60, 100_000),
            "rate_window_seconds": (60, 86_400),
            "max_inflight": (4, 128),
        }
        values = {}
        for name, (default, upper) in limits.items():
            variable = f"HEALTHQUERY_{name.upper()}"
            raw = os.environ.get(variable, str(default))
            if not re.fullmatch(r"[0-9]{1,9}", raw) or not 1 <= int(raw) <= upper:
                raise ValueError(f"{variable} must be an integer between 1 and {upper}.")
            values[name] = int(raw)
        return cls(**values)


class _BodyTooLarge(Exception):
    pass


class _ClientDisconnected(Exception):
    pass


class _BodyTimedOut(Exception):
    pass


class ServiceGuard:
    """Limits are per process; forwarded IP headers are deliberately not trusted."""

    def __init__(self, app, settings, time_provider=time.monotonic):
        self.app = app
        self.settings = settings
        self.clock = time_provider
        self.clients = OrderedDict()
        self.max_clients = 4096
        self.inflight = 0

    def _retry_after(self, client):
        now = self.clock()
        start, count = self.clients.pop(client, (now, 0))
        if now - start >= self.settings.rate_window_seconds:
            start, count = now, 0
        allowed = count < self.settings.rate_limit
        self.clients[client] = (start, count + int(allowed))
        if len(self.clients) > self.max_clients:
            self.clients.popitem(last=False)
        if allowed:
            return 0
        return max(1, math.ceil(self.settings.rate_window_seconds - (now - start)))

    async def _read_body(self, receive):
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise _ClientDisconnected
            if message["type"] != "http.request":
                raise RuntimeError("Unexpected ASGI request message.")
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.settings.body_limit_bytes:
                raise _BodyTooLarge
            body.extend(chunk)
            if not message.get("more_body", False):
                return bytes(body)

    @staticmethod
    async def _error(send, status, detail, retry_after=None):
        body = json.dumps({"detail": detail}).encode("utf-8")
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        if retry_after is not None:
            headers.append((b"retry-after", str(retry_after).encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        is_query = path == "/api/query" and scope.get("method") == "POST"
        limited = path == "/api/query" or path.startswith("/api/sources/")
        known = {"/api/query", "/api/info", "/health", "/ready"}
        route = path if path in known else "/api/sources/{id}" if path.startswith("/api/sources/") else "other"
        request_id = uuid4().hex
        started_at = self.clock()
        status, response_started, acquired = 499, False, False
        error_type = None

        async def guarded_send(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status, response_started = message["status"], True
                headers = dict(SECURITY_HEADERS)
                headers[b"x-request-id"] = request_id.encode()
                if path.startswith("/api/"):
                    headers[b"cache-control"] = b"no-store"
                original = [(key, value) for key, value in message.get("headers", []) if key.lower() not in headers]
                message = {**message, "headers": original + list(headers.items())}
            await send(message)

        try:
            if limited:
                client = (scope.get("client") or ("unknown",))[0]
                retry = self._retry_after(client)
                if retry:
                    await self._error(guarded_send, 429, "Too many requests. Please try again shortly.", retry)
                    return
            if is_query:
                if self.inflight >= self.settings.max_inflight:
                    await self._error(guarded_send, 503, "The service is busy. Please try again shortly.", 1)
                    return
                # No await separates the check and increment on this worker's event loop.
                self.inflight += 1
                acquired = True
                lengths = [value for key, value in scope.get("headers", []) if key.lower() == b"content-length"]
                if lengths:
                    if len(lengths) != 1 or not re.fullmatch(rb"[0-9]+", lengths[0]):
                        await self._error(guarded_send, 400, "Invalid Content-Length header.")
                        return
                    if len(lengths[0]) > 20 or int(lengths[0]) > self.settings.body_limit_bytes:
                        raise _BodyTooLarge
                try:
                    body = await asyncio.wait_for(self._read_body(receive), timeout=5)
                except TimeoutError as error:
                    raise _BodyTimedOut from error
                pending = True

                async def replay_receive():
                    nonlocal pending
                    if pending:
                        pending = False
                        return {"type": "http.request", "body": body, "more_body": False}
                    return await receive()

                await self.app(scope, replay_receive, guarded_send)
            else:
                await self.app(scope, receive, guarded_send)
        except _BodyTooLarge:
            await self._error(guarded_send, 413, "The request body is too large.")
        except _BodyTimedOut:
            await self._error(guarded_send, 408, "The request body took too long to arrive.")
        except _ClientDisconnected:
            pass
        except Exception as error:
            error_type = type(error).__name__
            if response_started:
                raise RuntimeError("Response interrupted.") from None
            await self._error(guarded_send, 500, "An unexpected service error occurred.")
        finally:
            if acquired:
                self.inflight -= 1
            method = scope.get("method", "")
            method = method if method in {"GET", "POST", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE", "TRACE", "CONNECT"} else "OTHER"
            event = {"request_id": request_id, "method": method, "route": route,
                     "status": status, "duration_ms": round((self.clock() - started_at) * 1000, 2)}
            if error_type is not None:
                event["error_type"] = error_type
            ACCESS_LOG.info(json.dumps(event, separators=(",", ":")))
