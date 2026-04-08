from __future__ import annotations

from app.application.bot.handlers.candidate.dashboard import (
    CandidateDashboardHandlersMixin,
)
from app.application.bot.handlers.candidate.file_contact import (
    CandidateFileContactHandlersMixin,
)
from app.application.bot.handlers.candidate.profile_submit import (
    CandidateProfileSubmitHandlersMixin,
)
from app.application.bot.handlers.common.bootstrap import (
    BootstrapRegistrationHandlersMixin,
)
from app.application.bot.handlers.common.callback_context import (
    CallbackContextMixin,
)
from app.application.bot.handlers.common.commands import (
    CommandHandlersMixin,
)
from app.application.bot.handlers.common.draft_conflicts import (
    DraftConflictHandlersMixin,
)
from app.application.bot.handlers.common.entrypoint import (
    EntrypointHandlersMixin,
)
from app.application.bot.handlers.common.gateway import GatewayUtilsMixin
from app.application.bot.handlers.common.pagination import (
    PaginationUtilsMixin,
)
from app.application.bot.handlers.common.profile_edit import (
    ProfileEditUtilsMixin,
)
from app.application.bot.handlers.common.recovery import RecoveryHandlersMixin
from app.application.bot.handlers.common.render import RenderUtilsMixin
from app.application.bot.handlers.common.search_utils import SearchUtilsMixin
from app.application.bot.handlers.common.stateful_messages import (
    StatefulMessageHandlersMixin,
)
from app.application.bot.handlers.common.utils import CommonUtilsMixin
from app.application.bot.handlers.employer.dashboard import (
    EmployerDashboardHandlersMixin,
)
from app.application.bot.handlers.employer.files import (
    EmployerFileHandlersMixin,
)
from app.application.bot.handlers.employer.profile_submit import (
    EmployerProfileSubmitHandlersMixin,
)
from app.application.bot.handlers.employer.search import (
    EmployerSearchHandlersMixin,
)
from app.application.bot.ui.keyboards import BotKeyboardsMixin
from app.application.bot.ui.messages import BotMessagesMixin
from app.application.bot.ui.profile_messages import BotProfileMessagesMixin
from app.application.bot.ui.search_wizard_messages import BotSearchWizardMessagesMixin


class UpdateRouterHandlers(
    CommonUtilsMixin,
    EntrypointHandlersMixin,
    RecoveryHandlersMixin,
    StatefulMessageHandlersMixin,
    ProfileEditUtilsMixin,
    BootstrapRegistrationHandlersMixin,
    CommandHandlersMixin,
    CandidateFileContactHandlersMixin,
    CandidateProfileSubmitHandlersMixin,
    EmployerFileHandlersMixin,
    EmployerProfileSubmitHandlersMixin,
    EmployerSearchHandlersMixin,
    DraftConflictHandlersMixin,
    EmployerDashboardHandlersMixin,
    CandidateDashboardHandlersMixin,
    CallbackContextMixin,
    GatewayUtilsMixin,
    SearchUtilsMixin,
    PaginationUtilsMixin,
    RenderUtilsMixin,
    BotKeyboardsMixin,
    BotMessagesMixin,
    BotProfileMessagesMixin,
    BotSearchWizardMessagesMixin,
):
    pass
