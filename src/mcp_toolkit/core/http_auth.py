from __future__ import annotations

from hmac import compare_digest

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def _same_secret(left: str, right: str) -> bool:
    return compare_digest(left.encode("utf-8"), right.encode("utf-8"))


class HeaderAuthMiddleware:
    def __init__(self, app: ASGIApp, *, header_name: str, token: str) -> None:
        self.app = app
        self.header_name = header_name
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        value = headers.get(self.header_name)
        if value is not None and self._valid_header(value):
            await self.app(scope, receive, send)
            return

        response = JSONResponse({"error": "unauthorized"}, status_code=401)
        await response(scope, receive, send)

    def _valid_header(self, value: str) -> bool:
        if _same_secret(value, self.token):
            return True
        if self.header_name.lower() != "authorization":
            return False
        prefix = "Bearer "
        return value.startswith(prefix) and _same_secret(value[len(prefix) :], self.token)
