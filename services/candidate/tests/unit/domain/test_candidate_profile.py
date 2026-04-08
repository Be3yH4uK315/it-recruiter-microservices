from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.domain.candidate.entities import (
    UNSET,
    CandidateAvatarDeleted,
    CandidateAvatarReplaced,
    CandidateCreated,
    CandidateProfileUpdated,
    CandidateResumeDeleted,
    CandidateResumeReplaced,
)
from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    SkillKind,
    WorkMode,
)
from app.domain.candidate.errors import CannotUnblockYourselfError
from app.domain.candidate.value_objects import (
    AvatarRef,
    CandidateSkillVO,
    ExperienceItemVO,
    ResumeRef,
    SalaryRange,
)


def test_candidate_profile_create_emits_candidate_created(candidate_profile) -> None:
    events = candidate_profile.pull_events()

    assert len(events) == 1
    assert isinstance(events[0], CandidateCreated)
    assert events[0].candidate_id == candidate_profile.id
    assert events[0].telegram_id == candidate_profile.telegram_id


def test_pull_events_clears_internal_queue(candidate_profile) -> None:
    first = candidate_profile.pull_events()
    second = candidate_profile.pull_events()

    assert len(first) == 1
    assert second == []


def test_update_profile_updates_fields_and_emits_event(candidate_profile) -> None:
    candidate_profile.pull_events()

    new_salary = SalaryRange.from_scalars(
        salary_min=300000,
        salary_max=450000,
        currency="RUB",
    )

    candidate_profile.update_profile(
        display_name="Дмитрий Петров",
        headline_role="Senior Python Developer",
        location="Berlin",
        work_modes=[WorkMode.REMOTE],
        contacts_visibility=ContactsVisibility.PUBLIC,
        contacts={"email": "new@example.com", "telegram": "@dmitry_new"},
        about_me="Updated bio",
        salary_range=new_salary,
        skills=[
            CandidateSkillVO(
                skill="python",
                kind=SkillKind.HARD,
                level=5,
            ),
        ],
    )

    assert candidate_profile.display_name == "Дмитрий Петров"
    assert candidate_profile.headline_role == "Senior Python Developer"
    assert candidate_profile.location == "Berlin"
    assert candidate_profile.work_modes == [WorkMode.REMOTE]
    assert candidate_profile.contacts_visibility == ContactsVisibility.PUBLIC
    assert candidate_profile.contacts == {"email": "new@example.com", "telegram": "@dmitry_new"}
    assert candidate_profile.about_me == "Updated bio"
    assert candidate_profile.salary_range == new_salary
    assert candidate_profile.skills == [
        CandidateSkillVO(skill="python", kind=SkillKind.HARD, level=5),
    ]

    events = candidate_profile.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], CandidateProfileUpdated)


def test_update_profile_with_no_changes_emits_no_event(candidate_profile) -> None:
    candidate_profile.pull_events()

    candidate_profile.update_profile(
        display_name=UNSET,
        headline_role=UNSET,
        location=UNSET,
        work_modes=UNSET,
        contacts_visibility=UNSET,
        contacts=UNSET,
        status=UNSET,
        about_me=UNSET,
        salary_range=UNSET,
        skills=UNSET,
        education=UNSET,
        experiences=UNSET,
        projects=UNSET,
    )

    assert candidate_profile.pull_events() == []


def test_blocked_candidate_cannot_unblock_self(candidate_profile) -> None:
    candidate_profile.pull_events()
    candidate_profile.status = CandidateStatus.BLOCKED

    with pytest.raises(
        CannotUnblockYourselfError, match="candidate cannot change status while blocked"
    ):
        candidate_profile.update_profile(status=CandidateStatus.ACTIVE)


def test_replace_avatar_emits_event_with_old_file_id(candidate_profile) -> None:
    candidate_profile.pull_events()

    old_file_id = uuid4()
    candidate_profile.replace_avatar(file_id=old_file_id)
    candidate_profile.pull_events()

    new_file_id = uuid4()
    returned_old_file_id = candidate_profile.replace_avatar(file_id=new_file_id)

    assert returned_old_file_id == old_file_id
    assert candidate_profile.avatar == AvatarRef(file_id=new_file_id)

    events = candidate_profile.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], CandidateAvatarReplaced)
    assert events[0].new_file_id == new_file_id
    assert events[0].old_file_id == old_file_id


def test_delete_avatar_emits_event(candidate_profile) -> None:
    candidate_profile.pull_events()

    file_id = uuid4()
    candidate_profile.replace_avatar(file_id=file_id)
    candidate_profile.pull_events()

    deleted_file_id = candidate_profile.delete_avatar()

    assert deleted_file_id == file_id
    assert candidate_profile.avatar is None

    events = candidate_profile.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], CandidateAvatarDeleted)
    assert events[0].file_id == file_id


def test_delete_avatar_returns_none_when_avatar_absent(candidate_profile) -> None:
    candidate_profile.pull_events()

    deleted_file_id = candidate_profile.delete_avatar()

    assert deleted_file_id is None
    assert candidate_profile.pull_events() == []


def test_replace_resume_emits_event_with_old_file_id(candidate_profile) -> None:
    candidate_profile.pull_events()

    old_file_id = uuid4()
    candidate_profile.replace_resume(file_id=old_file_id)
    candidate_profile.pull_events()

    new_file_id = uuid4()
    returned_old_file_id = candidate_profile.replace_resume(file_id=new_file_id)

    assert returned_old_file_id == old_file_id
    assert candidate_profile.resume == ResumeRef(file_id=new_file_id)

    events = candidate_profile.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], CandidateResumeReplaced)
    assert events[0].new_file_id == new_file_id
    assert events[0].old_file_id == old_file_id


def test_delete_resume_emits_event(candidate_profile) -> None:
    candidate_profile.pull_events()

    file_id = uuid4()
    candidate_profile.replace_resume(file_id=file_id)
    candidate_profile.pull_events()

    deleted_file_id = candidate_profile.delete_resume()

    assert deleted_file_id == file_id
    assert candidate_profile.resume is None

    events = candidate_profile.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], CandidateResumeDeleted)
    assert events[0].file_id == file_id


def test_delete_resume_returns_none_when_resume_absent(candidate_profile) -> None:
    candidate_profile.pull_events()

    deleted_file_id = candidate_profile.delete_resume()

    assert deleted_file_id is None
    assert candidate_profile.pull_events() == []


def test_update_profile_replaces_experiences(candidate_profile) -> None:
    candidate_profile.pull_events()

    new_experience = ExperienceItemVO(
        company="NewCo",
        position="Tech Lead",
        start_date=date(2024, 1, 1),
        end_date=None,
        responsibilities="Architecture and leadership",
    )

    candidate_profile.update_profile(experiences=[new_experience])

    assert candidate_profile.experiences == [new_experience]

    events = candidate_profile.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], CandidateProfileUpdated)
