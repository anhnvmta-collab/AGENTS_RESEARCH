"""Local HTTP boundary: bounded bodies and error messages without echoed inputs."""

from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BodyLimitError(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        upload = scope["path"].endswith("/documents")
        limit = 201_000_000 if upload else 1_000_000
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = limit + 1
        if length > limit:
            await JSONResponse({"detail": "Request exceeds size limit"}, status_code=413)(
                scope, receive, send
            )
            return
        consumed = 0

        async def bounded_receive() -> Any:
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > limit:
                raise BodyLimitError()
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except BodyLimitError:
            await JSONResponse({"detail": "Request exceeds size limit"}, status_code=413)(
                scope, receive, send
            )
