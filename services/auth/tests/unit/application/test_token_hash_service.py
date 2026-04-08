from __future__ import annotations

from app.application.auth.services.token_hash_service import TokenHashService


def test_hash_token_returns_sha256_hex() -> None:
    service = TokenHashService()

    token_hash = service.hash_token("test-token")

    assert isinstance(token_hash, str)
    assert len(token_hash) == 64
    assert token_hash != "test-token"


def test_verify_token_returns_true_for_matching_token() -> None:
    service = TokenHashService()
    raw_token = "refresh-token-value"
    token_hash = service.hash_token(raw_token)

    assert service.verify_token(raw_token=raw_token, token_hash=token_hash) is True


def test_verify_token_returns_false_for_non_matching_token() -> None:
    service = TokenHashService()
    token_hash = service.hash_token("token-one")

    assert service.verify_token(raw_token="token-two", token_hash=token_hash) is False
