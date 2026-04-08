from app.application.bot.ui.profile_message_mixins import (
    CandidateProfileMessagesMixin,
    EmployerProfileMessagesMixin,
    SearchProfileMessagesMixin,
)


class BotProfileMessagesMixin(
    CandidateProfileMessagesMixin,
    EmployerProfileMessagesMixin,
    SearchProfileMessagesMixin,
):
    """Facade mixin for profile and card message builders."""

    pass
