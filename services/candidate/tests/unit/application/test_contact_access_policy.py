from __future__ import annotations

from app.application.candidates.services.contact_access_policy import ContactAccessPolicy
from app.domain.candidate.enums import ContactsVisibility


def test_public_contacts_are_visible(candidate_profile) -> None:
    policy = ContactAccessPolicy()
    candidate_profile.contacts_visibility = ContactsVisibility.PUBLIC

    decision = policy.evaluate(
        candidate=candidate_profile,
        employer_has_access=False,
    )

    assert decision.can_view_contacts is True
    assert decision.visibility == ContactsVisibility.PUBLIC


def test_hidden_contacts_are_not_visible(candidate_profile) -> None:
    policy = ContactAccessPolicy()
    candidate_profile.contacts_visibility = ContactsVisibility.HIDDEN

    decision = policy.evaluate(
        candidate=candidate_profile,
        employer_has_access=True,
    )

    assert decision.can_view_contacts is False
    assert decision.visibility == ContactsVisibility.HIDDEN


def test_on_request_contacts_visible_when_employer_has_access(candidate_profile) -> None:
    policy = ContactAccessPolicy()
    candidate_profile.contacts_visibility = ContactsVisibility.ON_REQUEST

    decision = policy.evaluate(
        candidate=candidate_profile,
        employer_has_access=True,
    )

    assert decision.can_view_contacts is True
    assert decision.visibility == ContactsVisibility.ON_REQUEST


def test_on_request_contacts_hidden_when_employer_has_no_access(candidate_profile) -> None:
    policy = ContactAccessPolicy()
    candidate_profile.contacts_visibility = ContactsVisibility.ON_REQUEST

    decision = policy.evaluate(
        candidate=candidate_profile,
        employer_has_access=False,
    )

    assert decision.can_view_contacts is False
    assert decision.visibility == ContactsVisibility.ON_REQUEST
