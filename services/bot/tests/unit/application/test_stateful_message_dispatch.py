from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.bot.constants import (
    EMPLOYER_SEARCH_ABOUT_MAX_LEN,
    EMPLOYER_SEARCH_ROLE_MAX_LEN,
    EMPLOYER_SEARCH_ROLE_MIN_LEN,
    EMPLOYER_SEARCH_TITLE_MAX_LEN,
    EMPLOYER_SEARCH_TITLE_MIN_LEN,
    STATE_CANDIDATE_CONTACT_REQUEST_AWAIT_ID,
    STATE_CANDIDATE_EDIT_ABOUT_ME,
    STATE_CANDIDATE_EDIT_CONTACT_EMAIL,
    STATE_CANDIDATE_EDIT_CONTACT_PHONE,
    STATE_CANDIDATE_EDIT_CONTACT_TELEGRAM,
    STATE_CANDIDATE_EDIT_DISPLAY_NAME,
    STATE_CANDIDATE_EDIT_EDUCATION,
    STATE_CANDIDATE_EDIT_EXPERIENCES,
    STATE_CANDIDATE_EDIT_HEADLINE_ROLE,
    STATE_CANDIDATE_EDIT_LOCATION,
    STATE_CANDIDATE_EDIT_PROJECTS,
    STATE_CANDIDATE_EDIT_SALARY,
    STATE_CANDIDATE_EDIT_SKILLS,
    STATE_CANDIDATE_FILE_AWAIT_AVATAR,
    STATE_CANDIDATE_FILE_AWAIT_RESUME,
    STATE_CANDIDATE_REG_DISPLAY_NAME,
    STATE_EMPLOYER_EDIT_COMPANY,
    STATE_EMPLOYER_EDIT_CONTACT_EMAIL,
    STATE_EMPLOYER_EDIT_CONTACT_PHONE,
    STATE_EMPLOYER_EDIT_CONTACT_TELEGRAM,
    STATE_EMPLOYER_EDIT_CONTACT_WEBSITE,
    STATE_EMPLOYER_FILE_AWAIT_AVATAR,
    STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
    STATE_EMPLOYER_REG_COMPANY,
    STATE_EMPLOYER_SEARCH_ABOUT,
    STATE_EMPLOYER_SEARCH_ENGLISH,
    STATE_EMPLOYER_SEARCH_EXPERIENCE,
    STATE_EMPLOYER_SEARCH_LOCATION,
    STATE_EMPLOYER_SEARCH_MUST_SKILLS,
    STATE_EMPLOYER_SEARCH_NICE_SKILLS,
    STATE_EMPLOYER_SEARCH_ROLE,
    STATE_EMPLOYER_SEARCH_SALARY,
    STATE_EMPLOYER_SEARCH_TITLE,
    STATE_EMPLOYER_SEARCH_WORK_MODES,
)
from app.application.bot.handlers.common.search_utils import SearchUtilsMixin
from app.application.bot.handlers.common.stateful_messages import StatefulMessageHandlersMixin
from app.schemas.telegram import TelegramMessage, TelegramUser


@dataclass
class DummyState:
    state_key: str
    role_context: str | None = None
    payload: dict | None = None


class DummyTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs)


class DummyStateful(StatefulMessageHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self.calls: list[tuple[str, dict]] = []

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None

    def __getattr__(self, name: str):
        if name.startswith("_handle_"):

            async def _handler(**kwargs):
                self.calls.append((name, kwargs))
                return {"status": "processed", "action": name, "kwargs": kwargs}

            return _handler
        raise AttributeError(name)


class DummyStatefulEmployerSearch(StatefulMessageHandlersMixin, SearchUtilsMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self.calls: list[tuple[str, dict]] = []

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None

    async def _set_state_and_render_wizard_step(self, **kwargs):
        self.calls.append(("wizard", kwargs))

    async def _render_employer_search_confirm_step(self, **kwargs):
        self.calls.append(("confirm", kwargs))

    async def _render_employer_search_work_modes_step(self, **kwargs):
        self.calls.append(("work_modes", kwargs))

    async def _render_employer_search_english_step(self, **kwargs):
        self.calls.append(("english", kwargs))

    async def _build_employer_search_wizard_controls_markup(self, **kwargs):
        return {"controls": kwargs}

    def _extract_payload_text(self, payload: dict | None, key: str) -> str | None:
        if not isinstance(payload, dict):
            return None
        raw = payload.get(key)
        if raw is None:
            return None
        normalized = str(raw).strip()
        return normalized or None


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


def make_message(text: str | None = "value") -> TelegramMessage:
    return TelegramMessage.model_validate(
        {
            "message_id": 1,
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "chat": {"id": 100, "type": "private"},
            "text": text,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state_key", [STATE_CANDIDATE_FILE_AWAIT_AVATAR, STATE_CANDIDATE_FILE_AWAIT_RESUME]
)
async def test_stateful_candidate_file_states_dispatch(state_key: str) -> None:
    sut = DummyStateful()
    result = await sut._handle_stateful_message(
        message=make_message(text=None),
        actor=make_actor(),
        state=DummyState(state_key=state_key),
    )
    assert result["action"] == "_handle_candidate_file_upload_state"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state_key", [STATE_EMPLOYER_FILE_AWAIT_AVATAR, STATE_EMPLOYER_FILE_AWAIT_DOCUMENT]
)
async def test_stateful_employer_file_states_dispatch(state_key: str) -> None:
    sut = DummyStateful()
    result = await sut._handle_stateful_message(
        message=make_message(text=None),
        actor=make_actor(),
        state=DummyState(state_key=state_key),
    )
    assert result["action"] == "_handle_employer_file_upload_state"


@pytest.mark.asyncio
async def test_stateful_empty_text_returns_validation_message() -> None:
    sut = DummyStateful()
    result = await sut._handle_stateful_message(
        message=make_message(text="   "),
        actor=make_actor(),
        state=DummyState(state_key=STATE_CANDIDATE_EDIT_DISPLAY_NAME),
    )

    assert result == {"status": "processed", "action": "empty_stateful_message"}
    assert len(sut._telegram_client.sent_messages) == 1


@pytest.mark.asyncio
async def test_stateful_registration_display_name_validation() -> None:
    sut = DummyStateful()
    result = await sut._handle_stateful_message(
        message=make_message(text="."),
        actor=make_actor(),
        state=DummyState(state_key=STATE_CANDIDATE_REG_DISPLAY_NAME),
    )

    assert result["action"] == "candidate_registration_display_name_invalid"
    assert len(sut._telegram_client.sent_messages) == 1


@pytest.mark.asyncio
async def test_stateful_registration_company_validation() -> None:
    sut = DummyStateful()
    result = await sut._handle_stateful_message(
        message=make_message(text="."),
        actor=make_actor(),
        state=DummyState(state_key=STATE_EMPLOYER_REG_COMPANY),
    )

    assert result["action"] == "employer_registration_company_invalid"
    assert len(sut._telegram_client.sent_messages) == 1


FORWARDING_CASES = [
    (STATE_CANDIDATE_EDIT_DISPLAY_NAME, "_handle_candidate_edit_submit", {"raw_value": "new"}),
    (STATE_CANDIDATE_EDIT_HEADLINE_ROLE, "_handle_candidate_edit_submit", {"raw_value": "new"}),
    (STATE_CANDIDATE_EDIT_LOCATION, "_handle_candidate_edit_submit", {"raw_value": "new"}),
    (
        STATE_CANDIDATE_EDIT_LOCATION,
        "_handle_candidate_edit_submit",
        {"raw_value": None, "input_text": "-"},
    ),
    (STATE_CANDIDATE_EDIT_ABOUT_ME, "_handle_candidate_edit_submit", {"raw_value": "new"}),
    (
        STATE_CANDIDATE_EDIT_ABOUT_ME,
        "_handle_candidate_edit_submit",
        {"raw_value": None, "input_text": "skip"},
    ),
    (STATE_CANDIDATE_EDIT_SALARY, "_handle_candidate_salary_submit", {}),
    (STATE_CANDIDATE_EDIT_SKILLS, "_handle_candidate_skills_submit", {}),
    (STATE_CANDIDATE_EDIT_EDUCATION, "_handle_candidate_education_submit", {}),
    (STATE_CANDIDATE_EDIT_EXPERIENCES, "_handle_candidate_experiences_submit", {}),
    (STATE_CANDIDATE_EDIT_PROJECTS, "_handle_candidate_projects_submit", {}),
    (
        STATE_CANDIDATE_EDIT_CONTACT_TELEGRAM,
        "_handle_candidate_contact_submit",
        {"raw_value": "new", "allow_clear": False},
    ),
    (
        STATE_CANDIDATE_EDIT_CONTACT_EMAIL,
        "_handle_candidate_contact_submit",
        {"raw_value": "new", "allow_clear": True},
    ),
    (
        STATE_CANDIDATE_EDIT_CONTACT_EMAIL,
        "_handle_candidate_contact_submit",
        {"raw_value": None, "allow_clear": True, "input_text": "-"},
    ),
    (
        STATE_CANDIDATE_EDIT_CONTACT_PHONE,
        "_handle_candidate_contact_submit",
        {"raw_value": "new", "allow_clear": True},
    ),
    (
        STATE_CANDIDATE_CONTACT_REQUEST_AWAIT_ID,
        "_handle_candidate_contact_request_lookup",
        {"raw_request_id": "new"},
    ),
    (STATE_EMPLOYER_EDIT_COMPANY, "_handle_employer_edit_company_submit", {"company": "new"}),
    (
        STATE_EMPLOYER_EDIT_CONTACT_TELEGRAM,
        "_handle_employer_contact_submit",
        {"contact_key": "telegram", "raw_value": "new"},
    ),
    (
        STATE_EMPLOYER_EDIT_CONTACT_EMAIL,
        "_handle_employer_contact_submit",
        {"contact_key": "email", "raw_value": "new"},
    ),
    (
        STATE_EMPLOYER_EDIT_CONTACT_PHONE,
        "_handle_employer_contact_submit",
        {"contact_key": "phone", "raw_value": "new"},
    ),
    (
        STATE_EMPLOYER_EDIT_CONTACT_WEBSITE,
        "_handle_employer_contact_submit",
        {"contact_key": "website", "raw_value": "new"},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("state_key, expected_action, expectations", FORWARDING_CASES)
async def test_stateful_forwarding_edit_states(
    state_key: str,
    expected_action: str,
    expectations: dict,
) -> None:
    sut = DummyStateful()

    input_text = expectations.get("input_text", "new")
    result = await sut._handle_stateful_message(
        message=make_message(text=input_text),
        actor=make_actor(),
        state=DummyState(state_key=state_key),
    )

    assert result["action"] == expected_action
    kwargs = result["kwargs"]
    for key, value in expectations.items():
        if key == "input_text":
            continue
        assert kwargs.get(key) == value


@pytest.mark.asyncio
async def test_stateful_unknown_state() -> None:
    sut = DummyStateful()
    result = await sut._handle_stateful_message(
        message=make_message(text="something"),
        actor=make_actor(),
        state=DummyState(state_key="unknown_state"),
    )

    assert result == {"status": "processed", "action": "unknown_state"}
    assert len(sut._telegram_client.sent_messages) == 1


@pytest.mark.asyncio
async def test_employer_search_title_branches() -> None:
    sut = DummyStatefulEmployerSearch()
    actor = make_actor()

    invalid = await sut._handle_stateful_message(
        message=make_message(text="x" * (EMPLOYER_SEARCH_TITLE_MIN_LEN - 1)),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_TITLE, payload={}),
    )
    assert invalid["action"] == "employer_search_title_invalid"

    too_long = await sut._handle_stateful_message(
        message=make_message(text="x" * (EMPLOYER_SEARCH_TITLE_MAX_LEN + 1)),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_TITLE, payload={}),
    )
    assert too_long["action"] == "employer_search_title_too_long"

    saved = await sut._handle_stateful_message(
        message=make_message(text="Python backend"),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_TITLE, payload={}),
    )
    assert saved["action"] == "employer_search_title_saved"

    saved_from_confirm = await sut._handle_stateful_message(
        message=make_message(text="Python backend"),
        actor=actor,
        state=DummyState(
            state_key=STATE_EMPLOYER_SEARCH_TITLE,
            payload={"_employer_search_edit_step": "title"},
        ),
    )
    assert saved_from_confirm["action"] == "employer_search_title_saved_from_confirm"


@pytest.mark.asyncio
async def test_employer_search_role_branches() -> None:
    sut = DummyStatefulEmployerSearch()
    actor = make_actor()

    reset = await sut._handle_stateful_message(
        message=make_message(text="Python"),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_ROLE, payload={}),
    )
    assert reset["action"] == "employer_search_reset"

    invalid = await sut._handle_stateful_message(
        message=make_message(text="x" * (EMPLOYER_SEARCH_ROLE_MIN_LEN - 1)),
        actor=actor,
        state=DummyState(
            state_key=STATE_EMPLOYER_SEARCH_ROLE,
            payload={"title": "Search"},
        ),
    )
    assert invalid["action"] == "employer_search_role_invalid"

    too_long = await sut._handle_stateful_message(
        message=make_message(text="x" * (EMPLOYER_SEARCH_ROLE_MAX_LEN + 1)),
        actor=actor,
        state=DummyState(
            state_key=STATE_EMPLOYER_SEARCH_ROLE,
            payload={"title": "Search"},
        ),
    )
    assert too_long["action"] == "employer_search_role_too_long"

    saved = await sut._handle_stateful_message(
        message=make_message(text="Python Backend"),
        actor=actor,
        state=DummyState(
            state_key=STATE_EMPLOYER_SEARCH_ROLE,
            payload={"title": "Search"},
        ),
    )
    assert saved["action"] == "employer_search_role_saved"

    saved_from_confirm = await sut._handle_stateful_message(
        message=make_message(text="Python Backend"),
        actor=actor,
        state=DummyState(
            state_key=STATE_EMPLOYER_SEARCH_ROLE,
            payload={"title": "Search", "_employer_search_edit_step": "role"},
        ),
    )
    assert saved_from_confirm["action"] == "employer_search_role_saved_from_confirm"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state_key,input_text,invalid_action,saved_action,saved_from_confirm_action,payload",
    [
        (
            STATE_EMPLOYER_SEARCH_MUST_SKILLS,
            "Python:",
            "employer_search_must_skills_invalid",
            "employer_search_must_skills_saved",
            "employer_search_must_skills_saved_from_confirm",
            {},
        ),
        (
            STATE_EMPLOYER_SEARCH_NICE_SKILLS,
            "Python:",
            "employer_search_nice_skills_invalid",
            "employer_search_nice_skills_saved",
            "employer_search_nice_skills_saved_from_confirm",
            {},
        ),
        (
            STATE_EMPLOYER_SEARCH_EXPERIENCE,
            "bad",
            "employer_search_experience_invalid",
            "employer_search_experience_saved",
            "employer_search_experience_saved_from_confirm",
            {},
        ),
        (
            STATE_EMPLOYER_SEARCH_SALARY,
            "bad",
            "employer_search_salary_invalid",
            "employer_search_salary_saved",
            "employer_search_salary_saved_from_confirm",
            {},
        ),
    ],
)
async def test_employer_search_numeric_and_skill_steps(
    state_key: str,
    input_text: str,
    invalid_action: str,
    saved_action: str,
    saved_from_confirm_action: str,
    payload: dict,
) -> None:
    sut = DummyStatefulEmployerSearch()
    actor = make_actor()

    invalid = await sut._handle_stateful_message(
        message=make_message(text=input_text),
        actor=actor,
        state=DummyState(state_key=state_key, payload=payload),
    )
    assert invalid["action"] == invalid_action

    valid_text = {
        STATE_EMPLOYER_SEARCH_MUST_SKILLS: "Python:4, FastAPI",
        STATE_EMPLOYER_SEARCH_NICE_SKILLS: "Docker, AWS:3",
        STATE_EMPLOYER_SEARCH_EXPERIENCE: "2-5",
        STATE_EMPLOYER_SEARCH_SALARY: "150000 250000 RUB",
    }[state_key]

    saved = await sut._handle_stateful_message(
        message=make_message(text=valid_text),
        actor=actor,
        state=DummyState(state_key=state_key, payload=payload),
    )
    assert saved["action"] == saved_action

    step_name = {
        STATE_EMPLOYER_SEARCH_MUST_SKILLS: "must_skills",
        STATE_EMPLOYER_SEARCH_NICE_SKILLS: "nice_skills",
        STATE_EMPLOYER_SEARCH_EXPERIENCE: "experience",
        STATE_EMPLOYER_SEARCH_SALARY: "salary",
    }[state_key]
    saved_from_confirm = await sut._handle_stateful_message(
        message=make_message(text=valid_text),
        actor=actor,
        state=DummyState(
            state_key=state_key,
            payload={"_employer_search_edit_step": step_name},
        ),
    )
    assert saved_from_confirm["action"] == saved_from_confirm_action


@pytest.mark.asyncio
async def test_employer_search_location_work_modes_english_about_branches() -> None:
    sut = DummyStatefulEmployerSearch()
    actor = make_actor()

    location_saved = await sut._handle_stateful_message(
        message=make_message(text="Moscow"),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_LOCATION, payload={}),
    )
    assert location_saved["action"] == "employer_search_location_saved"

    location_from_confirm = await sut._handle_stateful_message(
        message=make_message(text="Moscow"),
        actor=actor,
        state=DummyState(
            state_key=STATE_EMPLOYER_SEARCH_LOCATION,
            payload={"_employer_search_edit_step": "location"},
        ),
    )
    assert location_from_confirm["action"] == "employer_search_location_saved_from_confirm"

    work_modes_prompt = await sut._handle_stateful_message(
        message=make_message(text="ignored"),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_WORK_MODES, payload={}),
    )
    assert work_modes_prompt["action"] == "employer_search_work_modes_keyboard_prompt"

    english_prompt = await sut._handle_stateful_message(
        message=make_message(text="ignored"),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_ENGLISH, payload={}),
    )
    assert english_prompt["action"] == "employer_search_english_keyboard_prompt"

    too_long_about = await sut._handle_stateful_message(
        message=make_message(text="x" * (EMPLOYER_SEARCH_ABOUT_MAX_LEN + 1)),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_ABOUT, payload={}),
    )
    assert too_long_about["action"] == "employer_search_about_too_long"

    about_saved = await sut._handle_stateful_message(
        message=make_message(text="Strong backend team"),
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_SEARCH_ABOUT, payload={}),
    )
    assert about_saved["action"] == "employer_search_about_saved"
