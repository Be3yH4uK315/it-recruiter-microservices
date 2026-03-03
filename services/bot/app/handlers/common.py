from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import logging

from app.keyboards import inline
from app.states import candidate, employer
from app.core import config, messages
from app.services import api_client

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    logger.info(f"User {message.from_user.id} started /start")
    await message.answer(messages.Messages.Common.START, reply_markup=inline.get_role_selection_keyboard())

@router.callback_query(inline.RoleCallback.filter(F.role_name == "candidate"))
async def cq_select_candidate(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = callback.from_user
    logger.info(f"User {user.id} selected candidate role")
    await state.update_data(
        mode='register', 
        current_field='display_name',
        experiences=[],
        skills=[],
        projects=[],
        education=[]
    )
    await callback.message.edit_text(messages.Messages.Profile.ENTER_NAME)
    await state.set_state(candidate.CandidateFSM.entering_basic_info)

@router.callback_query(inline.RoleCallback.filter(F.role_name == "employer"))
async def cq_select_employer(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Логика:
    1. Идем в API, ищем профиль.
    2. Если нет -> создаем (get_or_create).
    3. Если в профиле нет 'company' -> просим ввести (FSM: entering_company_name).
    4. Если есть -> идем к фильтрам.
    """
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
        logger.info(f"Employer {user_id} has company '{company}'. Proceeding to filters.")
        await state.update_data(filter_step='role', filters={})
        await state.set_state(employer.EmployerSearch.entering_filters)
        await callback.message.edit_text(messages.Messages.EmployerSearch.STEP_1)
    else:
        logger.info(f"Employer {user_id} missing company name. Asking user.")
        await state.set_state(employer.EmployerSearch.entering_company_name)
        await callback.message.edit_text(messages.Messages.EmployerSearch.ENTER_COMPANY_NAME)

@router.message(employer.EmployerSearch.entering_company_name)
async def handle_company_name(message: Message, state: FSMContext):
    """Сохраняем введенное название компании в API."""
    company_name = message.text.strip()
    if len(company_name) < 2:
        await message.answer("Название слишком короткое. Попробуйте еще раз.")
        return

    data = await state.get_data()
    employer_profile = data.get("employer_profile")
    
    if not employer_profile:
        await message.answer(messages.Messages.Common.SESSION_TIMEOUT)
        await state.clear()
        return

    try:
        updated_profile = await api_client.employer_api_client.update_employer_profile(
            employer_profile["id"], 
            {"company": company_name}
        )
        
        if updated_profile:
            logger.info(f"Company name updated to '{company_name}' for user {message.from_user.id}")
            await state.update_data(employer_profile=updated_profile)
            await state.update_data(filter_step='role', filters={})
            await state.set_state(employer.EmployerSearch.entering_filters)
            await message.answer(messages.Messages.EmployerSearch.STEP_1)
        else:
            await message.answer(messages.Messages.Common.API_ERROR)
            
    except Exception as e:
        logger.error(f"Failed to update company name: {e}")
        await message.answer(messages.Messages.Common.API_ERROR)

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    logger.info(f"User {message.from_user.id} started /search")
    
    employer_profile = await api_client.employer_api_client.get_or_create_employer(
        message.from_user.id, message.from_user.username or "HR"
    )
    
    if employer_profile and not employer_profile.get("company"):
        await state.update_data(employer_profile=employer_profile)
        await state.set_state(employer.EmployerSearch.entering_company_name)
        await message.answer(messages.Messages.EmployerSearch.ENTER_COMPANY_NAME)
    else:
        await state.update_data(filter_step='role')
        await state.set_state(employer.EmployerSearch.entering_filters)
        await message.answer(messages.Messages.EmployerSearch.STEP_1)

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