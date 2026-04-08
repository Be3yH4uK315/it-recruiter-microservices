from dataclasses import dataclass

import pytest

from app.application.state.services import conversation_state_service as module_under_test


@dataclass
class FakeStateModel:
    telegram_user_id: int
    role_context: str | None
    state_key: str | None
    state_version: int
    payload: dict | None


class FakeConversationStateRepository:
    def __init__(self, _session) -> None:
        self.model: FakeStateModel | None = None
        self.active_count = 0
        self.cleared_user_id = None

    async def get_by_telegram_user_id(self, telegram_user_id: int):
        if self.model and self.model.telegram_user_id == telegram_user_id:
            return self.model
        return None

    async def set_state(
        self,
        *,
        telegram_user_id: int,
        role_context: str | None,
        state_key: str,
        payload: dict | None,
    ):
        self.model = FakeStateModel(
            telegram_user_id=telegram_user_id,
            role_context=role_context,
            state_key=state_key,
            state_version=1,
            payload=payload,
        )
        self.active_count = 1
        return self.model

    async def count_active_states(self) -> int:
        return self.active_count

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.cleared_user_id = telegram_user_id
        self.model = None
        self.active_count = 0


@pytest.mark.asyncio
async def test_get_state_returns_none_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        module_under_test, "ConversationStateRepository", FakeConversationStateRepository
    )

    service = module_under_test.ConversationStateService(session=object())

    assert await service.get_state(telegram_user_id=1) is None


@pytest.mark.asyncio
async def test_set_and_get_and_clear_state_refresh_metrics(monkeypatch) -> None:
    metric_values: list[int] = []

    monkeypatch.setattr(
        module_under_test, "ConversationStateRepository", FakeConversationStateRepository
    )
    monkeypatch.setattr(
        module_under_test, "set_active_conversations", lambda value: metric_values.append(value)
    )

    service = module_under_test.ConversationStateService(session=object())

    view = await service.set_state(
        telegram_user_id=10,
        role_context="candidate",
        state_key="profile_edit",
        payload={"step": 1},
    )

    assert view.telegram_user_id == 10
    assert view.role_context == "candidate"
    assert view.state_key == "profile_edit"
    assert view.payload == {"step": 1}
    assert metric_values[-1] == 1

    fetched = await service.get_state(telegram_user_id=10)
    assert fetched is not None
    assert fetched.telegram_user_id == 10

    await service.clear_state(telegram_user_id=10)
    assert service._repo.cleared_user_id == 10
    assert metric_values[-1] == 0
