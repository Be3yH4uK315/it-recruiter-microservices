from __future__ import annotations

from uuid import uuid4

from app.infrastructure.messaging.event_mapper import DefaultEventMapper


def test_candidate_created_maps_to_domain_and_search_messages(candidate_profile) -> None:
    mapper = DefaultEventMapper()
    events = candidate_profile.pull_events()

    mapped = mapper.map_domain_event(
        event=events[0],
        candidate=candidate_profile,
    )

    assert len(mapped) == 2

    routing_keys = [item[0] for item in mapped]
    assert "candidate.created" in routing_keys
    assert "search.candidate.sync.requested" in routing_keys

    payloads = {routing_key: payload for routing_key, payload in mapped}
    assert payloads["candidate.created"]["candidate_id"] == str(candidate_profile.id)
    assert payloads["candidate.created"]["telegram_id"] == candidate_profile.telegram_id
    assert payloads["search.candidate.sync.requested"]["operation"] == "upsert"
    assert payloads["search.candidate.sync.requested"]["snapshot"]["id"] == str(
        candidate_profile.id
    )


def test_candidate_profile_updated_maps_to_candidate_updated_and_search_sync(
    candidate_profile,
) -> None:
    mapper = DefaultEventMapper()
    candidate_profile.pull_events()

    candidate_profile.update_profile(display_name="Новый display name")
    event = candidate_profile.pull_events()[0]

    mapped = mapper.map_domain_event(
        event=event,
        candidate=candidate_profile,
    )

    assert len(mapped) == 2
    routing_keys = [item[0] for item in mapped]
    assert routing_keys == [
        "candidate.updated",
        "search.candidate.sync.requested",
    ]


def test_avatar_replaced_maps_cleanup_when_old_file_exists(candidate_profile) -> None:
    mapper = DefaultEventMapper()
    candidate_profile.pull_events()

    first_file_id = uuid4()
    candidate_profile.replace_avatar(file_id=first_file_id)
    candidate_profile.pull_events()

    second_file_id = uuid4()
    candidate_profile.replace_avatar(file_id=second_file_id)
    event = candidate_profile.pull_events()[0]

    mapped = mapper.map_domain_event(
        event=event,
        candidate=candidate_profile,
    )

    routing_keys = [item[0] for item in mapped]
    assert routing_keys == [
        "candidate.avatar.replaced",
        "search.candidate.sync.requested",
    ]
    assert mapped[0][1]["old_file_id"] == str(first_file_id)
    assert mapped[0][1]["new_file_id"] == str(second_file_id)


def test_avatar_deleted_maps_cleanup_and_search_sync(candidate_profile) -> None:
    mapper = DefaultEventMapper()
    candidate_profile.pull_events()

    file_id = uuid4()
    candidate_profile.replace_avatar(file_id=file_id)
    candidate_profile.pull_events()

    candidate_profile.delete_avatar()
    event = candidate_profile.pull_events()[0]

    mapped = mapper.map_domain_event(
        event=event,
        candidate=candidate_profile,
    )

    assert [item[0] for item in mapped] == [
        "candidate.avatar.deleted",
        "search.candidate.sync.requested",
    ]
    assert mapped[0][1]["file_id"] == str(file_id)


def test_resume_replaced_maps_cleanup_when_old_file_exists(candidate_profile) -> None:
    mapper = DefaultEventMapper()
    candidate_profile.pull_events()

    first_file_id = uuid4()
    candidate_profile.replace_resume(file_id=first_file_id)
    candidate_profile.pull_events()

    second_file_id = uuid4()
    candidate_profile.replace_resume(file_id=second_file_id)
    event = candidate_profile.pull_events()[0]

    mapped = mapper.map_domain_event(
        event=event,
        candidate=candidate_profile,
    )

    assert [item[0] for item in mapped] == [
        "candidate.resume.replaced",
        "search.candidate.sync.requested",
    ]
    assert mapped[0][1]["old_file_id"] == str(first_file_id)
    assert mapped[0][1]["new_file_id"] == str(second_file_id)


def test_resume_deleted_maps_cleanup_and_search_sync(candidate_profile) -> None:
    mapper = DefaultEventMapper()
    candidate_profile.pull_events()

    file_id = uuid4()
    candidate_profile.replace_resume(file_id=file_id)
    candidate_profile.pull_events()

    candidate_profile.delete_resume()
    event = candidate_profile.pull_events()[0]

    mapped = mapper.map_domain_event(
        event=event,
        candidate=candidate_profile,
    )

    assert [item[0] for item in mapped] == [
        "candidate.resume.deleted",
        "search.candidate.sync.requested",
    ]
    assert mapped[0][1]["file_id"] == str(file_id)
