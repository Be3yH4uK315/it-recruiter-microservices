from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class TelegramApiError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class TelegramFileInfo:
    file_id: str
    file_unique_id: str | None
    file_path: str | None
    file_size: int | None


class TelegramApiClient:
    _MARKDOWN_V2_SPECIALS = frozenset("_*[]()~`>#+-=|{}.!")

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        bot_token: str,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._bot_token = bot_token

    @property
    def uses_placeholder_token(self) -> bool:
        return self._bot_token.startswith("change-me-")

    def _build_url(self, method: str) -> str:
        return f"{self._base_url}/bot{self._bot_token}/{method}"

    def _build_file_url(self, file_path: str) -> str:
        return f"{self._base_url}/file/bot{self._bot_token}/{file_path.lstrip('/')}"

    async def get_me(self) -> dict:
        return await self._post("getMe", {})

    async def get_webhook_info(self) -> dict:
        return await self._post("getWebhookInfo", {})

    async def set_webhook(
        self,
        *,
        url: str,
        secret_token: str | None = None,
        allowed_updates: list[str] | None = None,
        drop_pending_updates: bool = False,
    ) -> dict:
        payload: dict[str, object] = {
            "url": url,
            "drop_pending_updates": drop_pending_updates,
        }
        if secret_token is not None:
            payload["secret_token"] = secret_token
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates

        return await self._post("setWebhook", payload)

    async def delete_webhook(
        self,
        *,
        drop_pending_updates: bool = False,
    ) -> dict:
        payload: dict[str, object] = {
            "drop_pending_updates": drop_pending_updates,
        }
        return await self._post("deleteWebhook", payload)

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        normalized_parse_mode, normalized_text = self._normalize_text_parse_mode(
            text=text,
            parse_mode=parse_mode,
        )
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": normalized_text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if normalized_parse_mode is not None:
            payload["parse_mode"] = normalized_parse_mode

        if self.uses_placeholder_token:
            return {
                "message_id": 0,
                "chat": {"id": chat_id},
                "date": 0,
                "text": normalized_text,
            }

        return await self._post("sendMessage", payload)

    async def send_photo(
        self,
        *,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        normalized_parse_mode, normalized_caption = self._normalize_text_parse_mode(
            text=caption,
            parse_mode=parse_mode,
        )
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "photo": photo,
        }
        if normalized_caption is not None:
            payload["caption"] = normalized_caption
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if normalized_parse_mode is not None:
            payload["parse_mode"] = normalized_parse_mode
        if self.uses_placeholder_token:
            return {
                "message_id": 0,
                "chat": {"id": chat_id},
                "date": 0,
                "photo": [{"file_id": photo}],
            }
        return await self._post("sendPhoto", payload)

    async def send_document(
        self,
        *,
        chat_id: int,
        document: str,
        caption: str | None = None,
    ) -> dict:
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "document": document,
        }
        if caption is not None:
            payload["caption"] = caption
        if self.uses_placeholder_token:
            return {
                "message_id": 0,
                "chat": {"id": chat_id},
                "date": 0,
                "document": {"file_id": document},
            }
        return await self._post("sendDocument", payload)

    async def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        normalized_parse_mode, normalized_text = self._normalize_text_parse_mode(
            text=text,
            parse_mode=parse_mode,
        )
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": normalized_text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if normalized_parse_mode is not None:
            payload["parse_mode"] = normalized_parse_mode

        if self.uses_placeholder_token:
            return {
                "message_id": message_id,
                "chat": {"id": chat_id},
                "date": 0,
                "text": normalized_text,
            }

        return await self._post("editMessageText", payload)

    @classmethod
    def _normalize_text_parse_mode(
        cls,
        *,
        text: str | None,
        parse_mode: str | None,
    ) -> tuple[str | None, str | None]:
        if text is None or parse_mode is None:
            return parse_mode, text
        if parse_mode != "Markdown":
            return parse_mode, text
        return "MarkdownV2", cls._convert_markdown_to_markdown_v2(text)

    @classmethod
    def _convert_markdown_to_markdown_v2(cls, text: str) -> str:
        result: list[str] = []
        buffer: list[str] = []
        mode = "plain"
        i = 0
        text_len = len(text)

        def flush_buffer() -> None:
            if not buffer:
                return
            segment = "".join(buffer)
            buffer.clear()
            if mode == "code":
                result.append(cls._escape_markdown_v2_code(segment))
            else:
                result.append(cls._escape_markdown_v2_text(segment))

        while i < text_len:
            char = text[i]

            if char == "\\" and i + 1 < text_len:
                next_char = text[i + 1]
                if next_char in {"\\", "_", "*", "[", "]", "`"}:
                    buffer.append(next_char)
                    i += 2
                    continue

            if char == "`":
                flush_buffer()
                result.append("`")
                mode = "plain" if mode == "code" else "code"
                i += 1
                continue

            if char == "*" and mode != "code":
                flush_buffer()
                result.append("*")
                mode = "plain" if mode == "bold" else "bold"
                i += 1
                continue

            buffer.append(char)
            i += 1

        flush_buffer()
        return "".join(result)

    @classmethod
    def _escape_markdown_v2_text(cls, value: str) -> str:
        escaped: list[str] = []
        for char in value:
            if char == "\\" or char in cls._MARKDOWN_V2_SPECIALS:
                escaped.append(f"\\{char}")
            else:
                escaped.append(char)
        return "".join(escaped)

    @staticmethod
    def _escape_markdown_v2_code(value: str) -> str:
        escaped: list[str] = []
        for char in value:
            if char in {"\\", "`"}:
                escaped.append(f"\\{char}")
            else:
                escaped.append(char)
        return "".join(escaped)

    async def delete_message(
        self,
        *,
        chat_id: int,
        message_id: int,
    ) -> dict:
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "message_id": message_id,
        }

        if self.uses_placeholder_token:
            return {"ok": True, "result": True}

        return await self._post("deleteMessage", payload)

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict:
        payload: dict[str, object] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text is not None:
            payload["text"] = text

        if self.uses_placeholder_token:
            return {"callback_query_id": callback_query_id}

        return await self._post("answerCallbackQuery", payload)

    async def get_file(self, *, file_id: str) -> TelegramFileInfo:
        payload = await self._post("getFile", {"file_id": file_id})
        try:
            return TelegramFileInfo(
                file_id=str(payload["file_id"]),
                file_unique_id=(
                    str(payload["file_unique_id"]) if payload.get("file_unique_id") else None
                ),
                file_path=str(payload["file_path"]) if payload.get("file_path") else None,
                file_size=(
                    int(payload["file_size"]) if payload.get("file_size") is not None else None
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "telegram get_file response invalid",
                extra={"file_id": file_id, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise TelegramApiError("telegram api returned invalid getFile payload") from exc

    async def download_file_bytes(self, *, file_path: str) -> bytes:
        url = self._build_file_url(file_path)
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            logger.warning(
                "telegram file download failed",
                extra={"file_path": file_path, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise TelegramApiError("telegram file download failed") from exc

    async def _post(self, method: str, payload: dict) -> dict:
        try:
            response = await self._client.post(
                self._build_url(method),
                json=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            response_text: str | None = None
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                response_text = exc.response.text
            logger.warning(
                "telegram api request failed",
                extra={
                    "method": method,
                    "error_type": exc.__class__.__name__,
                    "response_text": response_text,
                },
                exc_info=exc,
            )
            raise TelegramApiError(f"telegram api request failed for method {method}") from exc

        if not isinstance(data, dict) or data.get("ok") is not True:
            logger.warning(
                "telegram api returned non-ok response",
                extra={"method": method, "response": data},
            )
            raise TelegramApiError(f"telegram api returned non-ok response for method {method}")

        result = data.get("result")
        if isinstance(result, dict):
            return result
        return {}
