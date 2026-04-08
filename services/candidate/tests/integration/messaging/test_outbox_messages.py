from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.db.models import candidate as db_models


async def test_create_candidate_writes_outbox_messages(client, session_factory) -> None:
    response = await client.post(
        "/candidates",
        json={
            "display_name": "Outbox Create",
            "headline_role": "Backend Engineer",
            "location": "Paris",
            "contacts": {"email": "outbox-create@example.com", "telegram": "@outbox_create"},
        },
    )
    assert response.status_code == 201, response.text
    candidate_id = response.json()["id"]

    async with session_factory() as session:
        result = await session.execute(
            select(db_models.OutboxMessage).order_by(db_models.OutboxMessage.created_at.asc()),
        )
        messages = list(result.scalars().all())

    assert len(messages) == 2

    routing_keys = [message.routing_key for message in messages]
    assert routing_keys == [
        "candidate.created",
        "search.candidate.sync.requested",
    ]

    created_payload = messages[0].message_body
    search_payload = messages[1].message_body

    assert created_payload["candidate_id"] == candidate_id
    assert created_payload["telegram_id"] == 777001

    assert search_payload["candidate_id"] == candidate_id
    assert search_payload["operation"] == "upsert"
    assert search_payload["snapshot"]["id"] == candidate_id
    assert search_payload["snapshot"]["display_name"] == "Outbox Create"


async def test_update_candidate_writes_outbox_messages(client, session_factory) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Before Update",
            "headline_role": "Python Developer",
            "contacts": {"email": "before-update@example.com", "telegram": "@before_update"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    async with session_factory() as session:
        await session.execute(db_models.OutboxMessage.__table__.delete())
        await session.commit()

    update_response = await client.patch(
        f"/candidates/{candidate_id}",
        json={
            "display_name": "After Update",
            "headline_role": "Senior Python Developer",
            "location": "Berlin",
        },
    )
    assert update_response.status_code == 200, update_response.text

    async with session_factory() as session:
        result = await session.execute(
            select(db_models.OutboxMessage).order_by(db_models.OutboxMessage.created_at.asc()),
        )
        messages = list(result.scalars().all())

    assert len(messages) == 2
    assert [message.routing_key for message in messages] == [
        "candidate.updated",
        "search.candidate.sync.requested",
    ]

    assert messages[0].message_body["candidate_id"] == candidate_id
    assert messages[1].message_body["snapshot"]["display_name"] == "After Update"
    assert messages[1].message_body["snapshot"]["location"] == "Berlin"


async def test_replace_avatar_with_previous_file_writes_cleanup_message(
    client, session_factory
) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Avatar Cleanup",
            "headline_role": "Engineer",
            "contacts": {"email": "avatar-cleanup@example.com", "telegram": "@avatar_cleanup"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    first_upload_url_response = await client.post(
        f"/candidates/{candidate_id}/avatar/upload-url",
        json={"filename": "avatar-1.png", "content_type": "image/png"},
    )
    assert first_upload_url_response.status_code == 200, first_upload_url_response.text

    first_replace = await client.put(
        f"/candidates/{candidate_id}/avatar",
        json={"file_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert first_replace.status_code == 204, first_replace.text

    async with session_factory() as session:
        await session.execute(db_models.OutboxMessage.__table__.delete())
        await session.commit()

    second_upload_url_response = await client.post(
        f"/candidates/{candidate_id}/avatar/upload-url",
        json={"filename": "avatar-2.png", "content_type": "image/png"},
    )
    assert second_upload_url_response.status_code == 200, second_upload_url_response.text

    second_replace = await client.put(
        f"/candidates/{candidate_id}/avatar",
        json={"file_id": "33333333-3333-3333-3333-333333333333"},
    )
    assert second_replace.status_code == 204, second_replace.text

    async with session_factory() as session:
        result = await session.execute(
            select(db_models.OutboxMessage).order_by(db_models.OutboxMessage.created_at.asc()),
        )
        messages = list(result.scalars().all())

    assert len(messages) == 2
    assert [message.routing_key for message in messages] == [
        "candidate.avatar.replaced",
        "search.candidate.sync.requested",
    ]

    replace_payload = messages[0].message_body
    search_payload = messages[1].message_body

    assert replace_payload["candidate_id"] == candidate_id
    assert replace_payload["new_file_id"] == "33333333-3333-3333-3333-333333333333"
    assert replace_payload["old_file_id"] == "11111111-1111-1111-1111-111111111111"

    assert search_payload["snapshot"]["avatar_file_id"] == "33333333-3333-3333-3333-333333333333"


async def test_delete_resume_writes_cleanup_message(client, session_factory) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Resume Cleanup",
            "headline_role": "Engineer",
            "contacts": {"email": "resume-cleanup@example.com", "telegram": "@resume_cleanup"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    upload_url_response = await client.post(
        f"/candidates/{candidate_id}/resume/upload-url",
        json={"filename": "resume.pdf", "content_type": "application/pdf"},
    )
    assert upload_url_response.status_code == 200, upload_url_response.text

    replace_response = await client.put(
        f"/candidates/{candidate_id}/resume",
        json={"file_id": "22222222-2222-2222-2222-222222222222"},
    )
    assert replace_response.status_code == 204, replace_response.text

    async with session_factory() as session:
        await session.execute(db_models.OutboxMessage.__table__.delete())
        await session.commit()

    delete_response = await client.delete(f"/candidates/{candidate_id}/resume")
    assert delete_response.status_code == 204, delete_response.text

    async with session_factory() as session:
        result = await session.execute(
            select(db_models.OutboxMessage).order_by(db_models.OutboxMessage.created_at.asc()),
        )
        messages = list(result.scalars().all())

    assert len(messages) == 2
    assert [message.routing_key for message in messages] == [
        "candidate.resume.deleted",
        "search.candidate.sync.requested",
    ]

    assert messages[0].message_body["file_id"] == "22222222-2222-2222-2222-222222222222"
    assert messages[1].message_body["snapshot"]["resume_file_id"] is None
