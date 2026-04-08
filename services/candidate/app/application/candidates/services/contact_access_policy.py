from __future__ import annotations

from dataclasses import dataclass

from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.enums import ContactsVisibility


@dataclass(slots=True, frozen=True)
class ContactAccessDecision:
    can_view_contacts: bool
    visibility: ContactsVisibility


class ContactAccessPolicy:
    def evaluate(
        self,
        *,
        candidate: CandidateProfile,
        employer_has_access: bool,
    ) -> ContactAccessDecision:
        if candidate.contacts_visibility == ContactsVisibility.PUBLIC:
            return ContactAccessDecision(
                can_view_contacts=True,
                visibility=candidate.contacts_visibility,
            )

        if candidate.contacts_visibility == ContactsVisibility.HIDDEN:
            return ContactAccessDecision(
                can_view_contacts=False,
                visibility=candidate.contacts_visibility,
            )

        return ContactAccessDecision(
            can_view_contacts=employer_has_access,
            visibility=candidate.contacts_visibility,
        )
