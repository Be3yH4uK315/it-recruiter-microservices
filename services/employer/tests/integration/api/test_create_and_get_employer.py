from __future__ import annotations


async def test_create_and_get_employer(client, employer_payload) -> None:
    create_response = await client.post("/api/v1/employers", json=employer_payload)
    assert create_response.status_code == 201, create_response.text

    created = create_response.json()
    assert created["telegram_id"] == 1001
    assert created["company"] == "Acme"
    assert created["contacts"]["email"] == "hr@acme.test"

    employer_id = created["id"]

    get_response = await client.get(f"/api/v1/employers/{employer_id}")
    assert get_response.status_code == 200, get_response.text

    fetched = get_response.json()
    assert fetched["id"] == employer_id
    assert fetched["telegram_id"] == 1001
    assert fetched["company"] == "Acme"
