from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings
from app.infrastructure.observability.logger import set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        self._header_name = settings.request_id_header_name
        self._expose_request_id_header = settings.expose_request_id_header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = self._extract_request_id(request)

        request.state.request_id = request_id
        set_request_id(request_id)

        try:
            response = await call_next(request)
        finally:
            set_request_id(None)

        if self._expose_request_id_header:
            response.headers[self._header_name] = request_id

        return response

    def _extract_request_id(self, request: Request) -> str:
        incoming = request.headers.get(self._header_name)
        if incoming and incoming.strip():
            return incoming.strip()
        return str(uuid4())
