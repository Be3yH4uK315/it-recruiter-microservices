from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.infrastructure.db.models.auth import IdempotencyKeyModel


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        session_factory: async_sessionmaker,
        header_name: str = "Idempotency-Key",
        methods: tuple[str, ...] = ("POST", "PUT", "PATCH", "DELETE"),
    ) -> None:
        super().__init__(app)
        self._session_factory = session_factory
        self._header_name = header_name
        self._methods = methods

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method.upper() not in self._methods:
            return await call_next(request)

        raw_key = request.headers.get(self._header_name)
        key = (raw_key or "").strip()
        if not key:
            return await call_next(request)

        raw_body = await request.body()
        request_hash = self._build_request_hash(
            method=request.method.upper(),
            path=request.url.path,
            body=raw_body,
        )

        existing = await self._get_existing_key(key)
        if existing is not None:
            if existing.request_hash != request_hash:
                return JSONResponse(
                    status_code=409,
                    content={"detail": "Idempotency key reuse with different payload"},
                    headers={self._header_name: key},
                )

            if existing.status_code == 204:
                return Response(
                    status_code=204,
                    headers={self._header_name: key},
                )

            return JSONResponse(
                status_code=existing.status_code,
                content=existing.response_body or {},
                headers={self._header_name: key},
            )

        async def receive() -> dict:
            return {
                "type": "http.request",
                "body": raw_body,
                "more_body": False,
            }

        request = Request(request.scope, receive)

        response = await call_next(request)
        response.headers[self._header_name] = key

        if response.status_code == 204:
            await self._store_response(
                key=key,
                request_hash=request_hash,
                response_body=None,
                status_code=response.status_code,
            )
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return response

        body_chunks = [chunk async for chunk in response.body_iterator]
        raw_response_body = b"".join(body_chunks)

        if not raw_response_body:
            response_body: dict | list | None = {}
        else:
            try:
                response_body = json.loads(raw_response_body.decode("utf-8"))
            except Exception:
                response_body = {
                    "detail": raw_response_body.decode("utf-8", errors="replace"),
                }

        await self._store_response(
            key=key,
            request_hash=request_hash,
            response_body=response_body,
            status_code=response.status_code,
        )

        headers = dict(response.headers)
        headers[self._header_name] = key

        return JSONResponse(
            status_code=response.status_code,
            content=response_body,
            headers=headers,
        )

    async def _get_existing_key(self, key: str) -> IdempotencyKeyModel | None:
        async with self._session_factory() as session:
            stmt = select(IdempotencyKeyModel).where(IdempotencyKeyModel.key == key)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _store_response(
        self,
        *,
        key: str,
        request_hash: str,
        response_body: dict | list | None,
        status_code: int,
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                IdempotencyKeyModel(
                    key=key,
                    request_hash=request_hash,
                    response_body=response_body,
                    status_code=status_code,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()

    @staticmethod
    def _build_request_hash(
        *,
        method: str,
        path: str,
        body: bytes,
    ) -> str:
        payload = method.encode("utf-8") + b"|" + path.encode("utf-8") + b"|" + body
        return hashlib.sha256(payload).hexdigest()
