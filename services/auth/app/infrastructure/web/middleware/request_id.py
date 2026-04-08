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
        self._expose_header = settings.expose_request_id_header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming_request_id = request.headers.get(self._header_name)
        request_id = (incoming_request_id or "").strip() or str(uuid4())

        request.state.request_id = request_id
        set_request_id(request_id)

        try:
            response = await call_next(request)
        finally:
            set_request_id(None)

        if self._expose_header:
            response.headers[self._header_name] = request_id

        return response
