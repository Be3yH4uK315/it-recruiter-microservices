from app.application.bot.ui.keyboard_mixins import (
    CandidateKeyboardsMixin,
    CommonKeyboardsMixin,
    EmployerKeyboardsMixin,
    SearchKeyboardsMixin,
)


class BotKeyboardsMixin(
    CommonKeyboardsMixin,
    CandidateKeyboardsMixin,
    EmployerKeyboardsMixin,
    SearchKeyboardsMixin,
):
    """Facade mixin for all bot keyboard builders."""

    pass
