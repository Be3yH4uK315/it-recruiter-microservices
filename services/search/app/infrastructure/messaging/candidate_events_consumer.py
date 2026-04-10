from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from uuid import UUID

import aio_pika
import httpx

from app.config import Settings
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

_PRIMARY_ROUTING_KEYS = (
    "search.candidate.sync.requested",
    "candidate.deleted",
    "candidate.status.changed",
)
_DEPRECATED_DUPLICATE_ROUTING_KEYS = (
    "candidate.created",
    "candidate.updated",
    "candidate.search_document.updated",
)


@dataclass(slots=True)
class CandidateEventsConsumer:
    settings: Settings
    http_client: httpx.AsyncClient

    async def run_forever(self, *, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._run(stop_event=stop_event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("candidate events consumer crashed")
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self.settings.rabbitmq_reconnect_delay_seconds,
                    )
                except asyncio.TimeoutError:
                    continue

    async def _run(self, *, stop_event: asyncio.Event) -> None:
        connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        try:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=self.settings.rabbitmq_prefetch_count)

            exchange = await channel.declare_exchange(
                self.settings.candidate_exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            queue = await channel.declare_queue(
                self.settings.candidate_queue_name,
                durable=True,
            )

            for routing_key in _DEPRECATED_DUPLICATE_ROUTING_KEYS:
                try:
                    await queue.unbind(exchange, routing_key)
                except Exception:
                    continue

            for routing_key in _PRIMARY_ROUTING_KEYS:
                await queue.bind(exchange, routing_key)

            logger.info(
                "candidate events consumer started",
                extra={
                    "queue": self.settings.candidate_queue_name,
                    "exchange": self.settings.candidate_exchange_name,
                },
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if stop_event.is_set():
                        break
                    try:
                        await self._handle_message(message)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception(
                            "candidate event handling failed",
                            extra={"routing_key": message.routing_key},
                        )
                        continue
        finally:
            await connection.close()

    async def _handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        if message.routing_key in _DEPRECATED_DUPLICATE_ROUTING_KEYS:
            logger.info(
                "skip deprecated duplicate candidate event",
                extra={"routing_key": message.routing_key},
            )
            await message.ack()
            return

        payload = self._decode_message_body(message.body)
        if payload is None:
            logger.warning("skip invalid message payload")
            await message.ack()
            return

        candidate_id = self._extract_candidate_id(payload)
        if candidate_id is None:
            logger.warning("skip message without candidate_id")
            await message.ack()
            return

        operation = self._resolve_operation(
            payload=payload,
            routing_key=message.routing_key,
        )

        try:
            if operation == "delete":
                await self._call_delete(candidate_id)
                logger.info(
                    "candidate delete dispatched to search api",
                    extra={
                        "candidate_id": str(candidate_id),
                        "event_type": message.routing_key,
                    },
                )
            else:
                await self._call_upsert(candidate_id)
                logger.info(
                    "candidate upsert dispatched to search api",
                    extra={
                        "candidate_id": str(candidate_id),
                        "event_type": message.routing_key,
                    },
                )
        except Exception:
            await message.reject(requeue=True)
            raise

        await message.ack()

    async def _call_upsert(self, candidate_id: UUID) -> None:
        url = (
            f"{self.settings.search_service_url.rstrip('/')}"
            f"/api/v1/internal/index/candidates/{candidate_id}"
        )
        response = await self.http_client.post(
            url,
            headers=self._build_internal_headers(),
            timeout=self.settings.internal_index_callback_timeout_seconds,
        )
        self._raise_for_status(response, "upsert", candidate_id)

    async def _call_delete(self, candidate_id: UUID) -> None:
        url = (
            f"{self.settings.search_service_url.rstrip('/')}"
            f"/api/v1/internal/index/candidates/{candidate_id}"
        )
        response = await self.http_client.delete(
            url,
            headers=self._build_internal_headers(),
            timeout=self.settings.internal_index_callback_timeout_seconds,
        )
        self._raise_for_status(response, "delete", candidate_id)

    def _build_internal_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self.settings.internal_service_token:
            headers["Authorization"] = f"Bearer {self.settings.internal_service_token}"
        return headers

    @staticmethod
    def _raise_for_status(
        response: httpx.Response,
        operation: str,
        candidate_id: UUID,
    ) -> None:
        if response.status_code < 400:
            return

        raise RuntimeError(
            f"search api {operation} failed for candidate {candidate_id}: "
            f"{response.status_code} {response.text}"
        )

    @staticmethod
    def _decode_message_body(body: bytes) -> dict | None:
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        return decoded if isinstance(decoded, dict) else None

    @staticmethod
    def _extract_candidate_id(payload: dict) -> UUID | None:
        raw = payload.get("candidate_id") or payload.get("id")
        if raw is None:
            return None

        try:
            return UUID(str(raw))
        except ValueError:
            return None

    @staticmethod
    def _resolve_operation(*, payload: dict, routing_key: str) -> str:
        operation = str(payload.get("operation") or "").strip().lower()
        if operation == "delete":
            return "delete"

        normalized_routing_key = routing_key.strip().lower()
        if normalized_routing_key.endswith(".deleted"):
            return "delete"

        return "upsert"
