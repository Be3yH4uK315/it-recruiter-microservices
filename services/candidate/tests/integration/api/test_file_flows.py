from __future__ import annotations


async def test_avatar_upload_url_and_replace_and_delete(client) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Avatar User",
            "headline_role": "Engineer",
            "contacts": {"email": "avatar@example.com", "telegram": "@avatar"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    upload_url_response = await client.post(
        f"/candidates/{candidate_id}/avatar/upload-url",
        json={
            "filename": "avatar.png",
            "content_type": "image/png",
        },
    )
    assert upload_url_response.status_code == 200, upload_url_response.text

    upload_payload = upload_url_response.json()
    assert upload_payload["file_id"] == "11111111-1111-1111-1111-111111111111"
    assert upload_payload["method"] == "PUT"

    replace_response = await client.put(
        f"/candidates/{candidate_id}/avatar",
        json={"file_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert replace_response.status_code == 204, replace_response.text

    get_response = await client.get(f"/candidates/{candidate_id}")
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["avatar_file_id"] == "11111111-1111-1111-1111-111111111111"

    delete_response = await client.delete(f"/candidates/{candidate_id}/avatar")
    assert delete_response.status_code == 204, delete_response.text

    get_response_after_delete = await client.get(f"/candidates/{candidate_id}")
    assert get_response_after_delete.status_code == 200, get_response_after_delete.text
    assert get_response_after_delete.json()["avatar_file_id"] is None


async def test_resume_upload_url_and_replace_and_delete(client) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Resume User",
            "headline_role": "Engineer",
            "contacts": {"email": "resume@example.com", "telegram": "@resume"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    upload_url_response = await client.post(
        f"/candidates/{candidate_id}/resume/upload-url",
        json={
            "filename": "resume.pdf",
            "content_type": "application/pdf",
        },
    )
    assert upload_url_response.status_code == 200, upload_url_response.text

    upload_payload = upload_url_response.json()
    assert upload_payload["file_id"] == "22222222-2222-2222-2222-222222222222"
    assert upload_payload["method"] == "PUT"

    replace_response = await client.put(
        f"/candidates/{candidate_id}/resume",
        json={"file_id": "22222222-2222-2222-2222-222222222222"},
    )
    assert replace_response.status_code == 204, replace_response.text

    get_response = await client.get(f"/candidates/{candidate_id}")
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["resume_file_id"] == "22222222-2222-2222-2222-222222222222"

    delete_response = await client.delete(f"/candidates/{candidate_id}/resume")
    assert delete_response.status_code == 204, delete_response.text

    get_response_after_delete = await client.get(f"/candidates/{candidate_id}")
    assert get_response_after_delete.status_code == 200, get_response_after_delete.text
    assert get_response_after_delete.json()["resume_file_id"] is None
