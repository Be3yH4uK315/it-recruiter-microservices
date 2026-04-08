from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    is_bot: bool = False
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: str | None = None


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message_id: int
    from_user: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat | None = None
    text: str | None = None
    photo: list["TelegramPhotoSize"] = Field(default_factory=list)
    document: TelegramDocument | None = None


class TelegramPhotoSize(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_id: str
    file_unique_id: str | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None


class TelegramDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_id: str
    file_unique_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class TelegramCallbackQuery(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    from_user: TelegramUser | None = Field(default=None, alias="from")
    message: TelegramMessage | None = None
    data: str | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    update_id: int
    message: TelegramMessage | None = None
    callback_query: TelegramCallbackQuery | None = None

    def detect_update_type(self) -> str:
        if self.callback_query is not None:
            return "callback_query"
        if self.message is not None:
            return "message"
        return "unknown"

    def actor(self) -> TelegramUser | None:
        if self.callback_query and self.callback_query.from_user:
            return self.callback_query.from_user
        if self.message and self.message.from_user:
            return self.message.from_user
        return None
