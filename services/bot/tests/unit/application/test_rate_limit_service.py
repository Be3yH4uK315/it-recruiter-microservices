from app.application.bot.services.rate_limit_service import RateLimitService


def test_message_rate_limit_blocks_after_threshold() -> None:
    service = RateLimitService(
        enabled=True,
        messages_per_second=2.0,
        callbacks_burst=3,
        callbacks_cooldown_seconds=1.0,
    )

    assert service.check_message(telegram_user_id=1).allowed is True
    assert service.check_message(telegram_user_id=1).allowed is True

    blocked = service.check_message(telegram_user_id=1)
    assert blocked.allowed is False
    assert blocked.reason == "message_rate_limited"


def test_message_rate_limit_disabled_allows_all() -> None:
    service = RateLimitService(
        enabled=False,
        messages_per_second=0.1,
        callbacks_burst=1,
        callbacks_cooldown_seconds=999.0,
    )

    for _ in range(10):
        result = service.check_message(telegram_user_id=42)
        assert result.allowed is True
        assert result.reason is None


def test_callback_rate_limit_enters_cooldown_after_burst() -> None:
    service = RateLimitService(
        enabled=True,
        messages_per_second=10.0,
        callbacks_burst=2,
        callbacks_cooldown_seconds=60.0,
    )

    assert service.check_callback(telegram_user_id=7).allowed is True
    assert service.check_callback(telegram_user_id=7).allowed is True

    burst_block = service.check_callback(telegram_user_id=7)
    assert burst_block.allowed is False
    assert burst_block.reason == "callback_rate_limited"

    cooldown_block = service.check_callback(telegram_user_id=7)
    assert cooldown_block.allowed is False
    assert cooldown_block.reason == "callback_cooldown"
