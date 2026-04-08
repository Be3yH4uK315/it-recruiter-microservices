from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.infrastructure.observability.logger import get_logger
from app.infrastructure.telegram.client import TelegramApiClient, TelegramApiError
from app.schemas.telegram import TelegramPhotoSize

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class TelegramUploadSource:
    telegram_file_id: str
    telegram_file_unique_id: str | None
    filename: str
    content_type: str


class BaseTelegramFileFlowService:
    """Shared helpers: pick photo, download from Telegram, PUT to presigned URL."""

    _flow_error_cls: type[Exception]

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        telegram_client: TelegramApiClient,
    ) -> None:
        self._http_client = http_client
        self._telegram_client = telegram_client

    @staticmethod
    def pick_best_photo(photos: list[TelegramPhotoSize]) -> TelegramPhotoSize | None:
        if not photos:
            return None
        return max(
            photos,
            key=lambda item: (
                item.file_size or 0,
                item.width or 0,
                item.height or 0,
            ),
        )

    async def _download_telegram_file(self, telegram_file_id: str) -> bytes:
        err_cls = self._flow_error_cls
        try:
            file_info = await self._telegram_client.get_file(file_id=telegram_file_id)
            if not file_info.file_path:
                raise err_cls("Telegram не вернул file_path для файла.")
            return await self._telegram_client.download_file_bytes(file_path=file_info.file_path)
        except TelegramApiError as exc:
            raise err_cls("Не удалось скачать файл из Telegram.") from exc

    async def _upload_to_presigned_url(
        self,
        *,
        upload_url: str,
        method: str,
        headers: dict[str, str],
        content_type: str,
        content: bytes,
    ) -> None:
        err_cls = self._flow_error_cls
        normalized_method = method.strip().upper() or "PUT"
        request_headers = dict(headers)
        if "Content-Type" not in request_headers:
            request_headers["Content-Type"] = content_type

        try:
            response = await self._http_client.request(
                normalized_method,
                upload_url,
                content=content,
                headers=request_headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "presigned upload failed",
                extra={
                    "method": normalized_method,
                    "content_type": content_type,
                    "upload_url_host": urlparse(upload_url).netloc,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            raise err_cls("Не удалось загрузить файл в файловое хранилище.") from exc
