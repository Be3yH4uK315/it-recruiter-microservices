import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.core import config, messages
from app.handlers.candidate import _show_profile
from app.keyboards import inline
from app.services import api_client
from app.states import candidate, employer

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    logger.info(f"User {message.from_user.id} started /start")
    await message.answer(
        messages.Messages.Common.START,
        reply_markup=inline.get_role_selection_keyboard(),
    )


@router.callback_query(inline.RoleCallback.filter(F.role_name == "candidate"))
async def cq_select_candidate(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = callback.from_user
    logger.info(f"User {user.id} selected candidate role")
    try:
        profile = await api_client.candidate_api_client.get_candidate_by_telegram_id(user.id)
        if profile:
            await state.update_data(mode="edit", profile_cache=profile)

            await callback.answer(messages.Messages.Profile.LOADING_PROFILE)
            await _show_profile(callback, state)
            return

    except api_client.APIHTTPError as e:
        if e.status_code == 404:
            pass
        else:
            logger.error(f"API Error fetching candidate profile: {e}")
            await callback.answer(messages.Messages.Common.API_ERROR, show_alert=True)
            return
    except Exception as e:
        logger.error(f"Network/Unexpected Error: {e}")
        await callback.answer(messages.Messages.Common.API_ERROR, show_alert=True)
        return

    await callback.answer()
    await state.update_data(
        mode="register",
        current_field="display_name",
        experiences=[],
        skills=[],
        projects=[],
        education=[],
    )

    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(messages.Messages.Profile.ENTER_NAME)
        else:
            await callback.message.edit_text(messages.Messages.Profile.ENTER_NAME)
    except Exception:
        await callback.message.answer(messages.Messages.Profile.ENTER_NAME)

    await state.set_state(candidate.CandidateFSM.entering_basic_info)


@router.callback_query(inline.RoleCallback.filter(F.role_name == "employer"))
async def cq_select_employer(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    employer_profile = await api_client.employer_api_client.get_or_create_employer(
        user_id, callback.from_user.username or "HR"
    )

    if not employer_profile:
        await callback.message.answer(messages.Messages.EmployerSearch.EMPLOYER_ERROR)
        return

    await state.update_data(employer_profile=employer_profile)

    company = employer_profile.get("company")
    if company:
        logger.info(f"Employer {user_id} has company '{company}'. Showing menu.")
        await state.set_state(employer.EmployerSearch.main_menu)
        await callback.message.edit_text(
            messages.Messages.EmployerMenu.MAIN_MENU, reply_markup=inline.get_employer_main_menu()
        )
    else:
        logger.info(f"Employer {user_id} missing company name. Asking user.")
        await state.set_state(employer.EmployerSearch.entering_company_name)
        await callback.message.edit_text(messages.Messages.EmployerSearch.ENTER_COMPANY_NAME)


@router.message(employer.EmployerSearch.entering_company_name)
async def handle_company_name(message: Message, state: FSMContext):
    """Сохраняем введенное название компании в API."""
    company_name = message.text.strip()
    if len(company_name) < 2:
        await message.answer(messages.Messages.EmployerSearch.COMPANY_NAME_ERROR)
        return

    data = await state.get_data()
    employer_profile = data.get("employer_profile")

    if not employer_profile:
        await message.answer(messages.Messages.Common.SESSION_TIMEOUT)
        await state.clear()
        return

    try:
        updated_profile = await api_client.employer_api_client.update_employer_profile(
            employer_profile["id"], {"company": company_name}
        )
        if updated_profile:
            await state.update_data(employer_profile=updated_profile)
            await state.set_state(employer.EmployerSearch.main_menu)
            await message.answer(
                messages.Messages.EmployerMenu.MAIN_MENU,
                reply_markup=inline.get_employer_main_menu(),
            )
        else:
            await message.answer(messages.Messages.Common.API_ERROR)
    except Exception as e:
        logger.error(f"Failed to update company name: {e}")
        await message.answer(messages.Messages.Common.API_ERROR)


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    employer_profile = await api_client.employer_api_client.get_or_create_employer(
        message.from_user.id, message.from_user.username or "HR"
    )
    if employer_profile and not employer_profile.get("company"):
        await state.update_data(employer_profile=employer_profile)
        await state.set_state(employer.EmployerSearch.entering_company_name)
        await message.answer(messages.Messages.EmployerSearch.ENTER_COMPANY_NAME)
    elif employer_profile:
        await state.update_data(employer_profile=employer_profile)
        await state.set_state(employer.EmployerSearch.main_menu)
        await message.answer(
            messages.Messages.EmployerMenu.MAIN_MENU, reply_markup=inline.get_employer_main_menu()
        )


@router.message(Command("admin_reindex"))
async def cmd_admin_reindex(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    await message.answer("⏳ Запускаю переиндексацию...")
    success = await api_client.search_api_client.trigger_reindex(message.from_user.id)
    if success:
        await message.answer("✅ Процесс запущен в фоне.")
    else:
        await message.answer("❌ Ошибка запуска. Проверь логи.")
