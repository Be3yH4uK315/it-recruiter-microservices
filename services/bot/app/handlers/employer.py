from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from typing import Dict, Any, Optional
import logging

from app.utils import validators
from app.states.employer import EmployerSearch
from app.services import api_client
from app.keyboards import inline
from app.utils import formatters
from app.core.messages import Messages

router = Router()
logger = logging.getLogger(__name__)

async def show_next_candidate(message: Message | CallbackQuery, state: FSMContext) -> None:
    """
    Запрашивает следующего кандидата у бэкенда и отображает его.
    """
    data: Dict[str, Any] = await state.get_data()
    session_id = data.get('session_id')
    target_message = message.message if isinstance(message, CallbackQuery) else message
    user_id = target_message.chat.id
    is_callback = isinstance(message, CallbackQuery)

    if not session_id:
         await target_message.answer(Messages.EmployerSearch.SESSION_EXPIRED)
         if is_callback: await message.answer()
         await state.clear()
         return

    try:
        candidate = await api_client.employer_api_client.get_next_candidate(session_id)
        
        if not candidate:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Изменить фильтры", callback_data="restart_search")]
            ])
            await target_message.answer(Messages.EmployerSearch.NO_MORE, reply_markup=keyboard)
            
            if is_callback: await message.answer()
            await state.clear()
            return

    except (api_client.APINetworkError, api_client.APIHTTPError) as e:
        logger.error(f"Error fetching next candidate for user {user_id}: {e}")
        await target_message.answer(Messages.Common.API_ERROR)
        if is_callback: await message.answer()
        return
    await state.update_data(current_candidate=candidate)
    
    candidate_id = str(candidate['id'])

    avatar_url: Optional[str] = None
    if candidate.get("avatars") and candidate["avatars"]:
        avatar_file_id = candidate["avatars"][0].get("file_id")
        if avatar_file_id:
            try:
                avatar_url = await api_client.file_api_client.get_download_url_by_file_id(avatar_file_id)
            except Exception: pass

    caption = formatters.format_candidate_profile(candidate, is_owner=False)
    has_resume = bool(candidate.get("resumes"))
    keyboard = inline.get_initial_search_keyboard(candidate_id, has_resume)
    current_message_is_photo = bool(target_message.photo)

    try:
        if avatar_url:
            media = InputMediaPhoto(media=avatar_url, caption=caption)
            if is_callback:
                if current_message_is_photo:
                    await target_message.edit_media(media=media, reply_markup=keyboard)
                else:
                    await target_message.delete(); await target_message.answer_photo(photo=avatar_url, caption=caption, reply_markup=keyboard)
            else:
                 await target_message.answer_photo(photo=avatar_url, caption=caption, reply_markup=keyboard)
        else:
             if is_callback:
                 if current_message_is_photo:
                     await target_message.delete(); await target_message.answer(text=caption, reply_markup=keyboard)
                 else:
                     await target_message.edit_text(text=caption, reply_markup=keyboard)
             else:
                 await target_message.answer(text=caption, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error displaying candidate profile media for user {user_id}: {e}", exc_info=True)
        try:
             await target_message.answer(text=caption, reply_markup=keyboard)
             if is_callback and current_message_is_photo: await target_message.delete()
        except Exception: pass

    if is_callback: await message.answer()

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    """Обработка команды /search."""
    await state.clear()
    logger.info(f"User {message.from_user.id} started search")
    await state.update_data(filter_step='role', filters={})
    await state.set_state(EmployerSearch.entering_filters)
    await message.answer(Messages.EmployerSearch.STEP_1)

@router.message(EmployerSearch.entering_filters)
async def handle_filter_input(message: Message, state: FSMContext) -> None:
    data: Dict[str, Any] = await state.get_data()
    filter_step: Optional[str] = data.get("filter_step")
    filters: Dict[str, Any] = data.get("filters", {})
    user_id = message.from_user.id

    if filter_step is None:
        await message.answer(Messages.Common.INVALID_INPUT); return

    try:
        next_step = None; prompt = None; input_text = message.text.strip() if message.text else ""
        keyboard = None

        if filter_step == "role":
            if not input_text: raise ValueError("Role empty")
            filters["role"] = input_text
            prompt = Messages.EmployerSearch.STEP_2; next_step = "must_skills"
        
        elif filter_step == "must_skills":
            skills = [s.strip().lower() for s in input_text.split(",") if s.strip()]
            if not skills: raise ValueError("Must skills empty")
            filters["must_skills"] = skills
            prompt = Messages.EmployerSearch.STEP_3; next_step = "nice_skills"
        
        elif filter_step == "nice_skills":
            if input_text != "/skip":
                skills = [s.strip().lower() for s in input_text.split(",") if s.strip()]
                if skills: filters["nice_skills"] = skills
            prompt = Messages.EmployerSearch.STEP_4; next_step = "experience"
        
        elif filter_step == "experience":
            parts = input_text.replace(",", ".").split("-")
            try:
                exp_min = float(parts[0].strip())
                exp_max = float(parts[1].strip()) if len(parts) > 1 else None
                if exp_min < 0: raise ValueError
                filters["experience_min"] = exp_min
                filters["experience_max"] = exp_max
            except ValueError:
                await message.answer("Введите число или диапазон (например: 2-5).")
                return

            prompt = Messages.EmployerSearch.STEP_5; next_step = "location"
        
        elif filter_step == "location":
             if input_text != "/skip": filters["location"] = input_text
             prompt = "🇬🇧 Какой минимальный уровень английского требуется?"
             next_step = "english_level"
             keyboard = inline.get_english_level_keyboard()

             await state.update_data(filter_step=next_step, filters=filters)
             await message.answer(prompt, reply_markup=keyboard)
             return
             
        elif filter_step == "salary":
             if input_text == "/skip":
                 salary_data = {}
             else:
                 salary_data = validators.parse_salary(input_text)
                 if not salary_data:
                     await message.answer(
                         "❌ Не удалось распознать бюджет.\n"
                         "Введите число (например: <b>200000</b>) или нажмите /skip."
                     )
                     return
             if salary_data.get("salary_min") and not salary_data.get("salary_max"):
                 filters["salary_max"] = salary_data["salary_min"]
             elif salary_data.get("salary_max"):
                 filters["salary_max"] = salary_data["salary_max"]
             
             filters["currency"] = salary_data.get("currency", "RUB")
             
             prompt = Messages.EmployerSearch.STEP_6
             next_step = "work_modes"
             keyboard = inline.get_work_modes_keyboard(selected=set())

        elif filter_step == "work_modes":
             await message.answer("Пожалуйста, используйте кнопки для выбора формата.", reply_markup=inline.get_work_modes_keyboard(selected=set(filters.get("work_modes", []))))
             return

        await state.update_data(filter_step=next_step, filters=filters)
        if prompt:
            await message.answer(prompt, reply_markup=keyboard)

    except ValueError:
        await message.answer(Messages.Common.INVALID_INPUT)
    except Exception as e:
         logger.error(f"Error filter input user {user_id}: {e}", exc_info=True)
         await message.answer(Messages.Common.API_ERROR); await state.clear()

@router.callback_query(inline.WorkModeCallback.filter(), EmployerSearch.entering_filters)
async def handle_employer_work_mode(callback: CallbackQuery, callback_data: inline.WorkModeCallback, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("filter_step") != "work_modes":
        await callback.answer()
        return

    filters = data.get("filters", {})
    
    current_modes = filters.get("work_modes", [])
    if not isinstance(current_modes, list):
        current_modes = []
        
    selected_modes = set(current_modes)
    mode = callback_data.mode

    if mode == "done":
        readable_modes = [formatters.WORK_MODES_MAP.get(m, m) for m in selected_modes]
        final_text = f"✅ Выбрано: <b>{', '.join(readable_modes) if readable_modes else 'Любой формат'}</b>"
        
        try:
            await callback.message.edit_text(final_text)
        except Exception:
            pass
        
        f = filters
        summary = (
            "🔎 <b>Параметры поиска:</b>\n"
            f"• Роль: {f.get('role')}\n"
            f"• Навыки: {', '.join(f.get('must_skills', []))}\n"
        )
        if f.get('experience_min'):
            summary += f"• Опыт: от {f['experience_min']} лет\n"
        if f.get('salary_max'):
            summary += f"• Бюджет: до {f['salary_max']} {f.get('currency','RUB')}\n"
        if readable_modes:
            summary += f"• Формат: {', '.join(readable_modes)}\n"
            
        await callback.message.answer(summary)
        await callback.message.answer(Messages.EmployerSearch.SAVING)
        
        user_id = callback.from_user.id
        employer_profile = data.get('employer_profile') 
        if not employer_profile:
             employer_profile = await api_client.employer_api_client.get_or_create_employer(user_id, callback.from_user.username or "HR")
             await state.update_data(employer_profile=employer_profile)
        
        if not employer_profile:
             await callback.message.answer(Messages.EmployerSearch.EMPLOYER_ERROR)
             await state.clear()
             return

        search_session = await api_client.employer_api_client.create_search_session(employer_profile["id"], filters)
        
        if not search_session:
             await callback.message.answer(Messages.EmployerSearch.SEARCH_ERROR)
             await state.clear()
             return
        
        await state.update_data(session_id=search_session["id"])
        await state.set_state(EmployerSearch.showing_results)
        from app.handlers.employer import show_next_candidate
        await show_next_candidate(callback, state)
        
    else:
        if mode in selected_modes: 
            selected_modes.remove(mode)
        else: 
            selected_modes.add(mode)
        
        updated_list = list(selected_modes)
        filters["work_modes"] = updated_list
        await state.update_data(filters=filters)
        
        readable_modes = [formatters.WORK_MODES_MAP.get(m, m) for m in updated_list]
        current_selection_text = f"\n\n👉 <b>Текущий выбор:</b> {', '.join(readable_modes) if readable_modes else 'Любой формат'}"
        
        try:
            await callback.message.edit_text(
                Messages.EmployerSearch.STEP_6 + current_selection_text, 
                reply_markup=inline.get_work_modes_keyboard(selected=selected_modes)
            )
        except Exception:
            pass
    
    await callback.answer()

@router.callback_query(inline.EnglishLevelCallback.filter(), EmployerSearch.entering_filters)
async def handle_employer_english_level(callback: CallbackQuery, callback_data: inline.EnglishLevelCallback, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("filter_step") != "english_level":
        await callback.answer()
        return

    filters = data.get("filters", {})
    level = None if callback_data.level == "skip" else callback_data.level
    
    if level:
        filters["english_level"] = level
        
    await state.update_data(filters=filters, filter_step="salary")
    
    text_level = f"<b>{level}</b>" if level else "<b>Любой</b>"
    try:
        await callback.message.edit_text(f"✅ Требуемый английский: {text_level}")
    except Exception: pass
    
    await callback.message.answer("💰 Укажите максимальный бюджет (например: 200к, 3000$) или /skip:")
    await callback.answer()


@router.callback_query(inline.SearchResultDecision.filter(), EmployerSearch.showing_results)
async def handle_decision(callback: CallbackQuery, callback_data: inline.SearchResultDecision, state: FSMContext) -> None:
    data: Dict[str, Any] = await state.get_data()
    session_id: Optional[str] = data.get("session_id")

    if not session_id:
        await callback.answer(Messages.EmployerSearch.SESSION_EXPIRED, show_alert=True); return

    try:
        success = await api_client.employer_api_client.save_decision(
            session_id=session_id, candidate_id=callback_data.candidate_id, decision=callback_data.action
        )
        if not success:
            await callback.answer(Messages.EmployerSearch.DECISION_ERROR, show_alert=True); return

        if callback_data.action == "like":
            await callback.answer(Messages.EmployerSearch.DECISION_LIKE)
            data = await state.get_data()
            cand = data.get("current_candidate", {})
            visibility = cand.get("contacts_visibility", "on_request")
            
            new_keyboard = inline.get_liked_candidate_keyboard(callback_data.candidate_id, visibility)
            await callback.message.edit_reply_markup(reply_markup=new_keyboard)
        else:
            await callback.answer("Скрыт.")
            await show_next_candidate(callback, state)

    except Exception as e:
        logger.error(f"Error saving decision: {e}")
        await callback.answer(Messages.EmployerSearch.DECISION_ERROR, show_alert=True)

@router.callback_query(inline.SearchResultAction.filter(F.action == "next"), EmployerSearch.showing_results)
async def handle_next_candidate(callback: CallbackQuery, callback_data: inline.SearchResultAction, state: FSMContext) -> None:
    data: Dict[str, Any] = await state.get_data()
    session_id: Optional[str] = data.get("session_id")
    current_candidate = data.get("current_candidate")
    
    if not session_id or not current_candidate:
        await callback.answer("Ошибка сессии.", show_alert=True)
        return

    try:
        await api_client.employer_api_client.save_decision(
            session_id=session_id, 
            candidate_id=current_candidate["id"], 
            decision="skip"
        )
    except Exception as e:
        logger.error(f"Failed to save skip decision: {e}")
    
    await callback.answer()
    
    await show_next_candidate(callback, state)

@router.callback_query(inline.SearchResultAction.filter(F.action == "contact"), EmployerSearch.showing_results)
async def handle_show_contact(callback: CallbackQuery, callback_data: inline.SearchResultAction, state: FSMContext) -> None:
    data = await state.get_data()
    employer_profile = data.get('employer_profile')
    
    if not employer_profile:
        employer_profile = await api_client.employer_api_client.get_or_create_employer(
            callback.from_user.id, callback.from_user.username or "HR"
        )
        if employer_profile:
            await state.update_data(employer_profile=employer_profile)
        else:
            await callback.answer("Ошибка сессии.", show_alert=True)
            return

    candidate_id = callback_data.candidate_id
    await callback.answer(Messages.EmployerSearch.CONTACTS_REQUEST, show_alert=False)

    try:
        response = await api_client.employer_api_client.request_contacts(
            employer_id=employer_profile['id'], candidate_id=candidate_id
        )
        
        if response and response.get("granted"):
            contacts = response.get("contacts")
            if contacts:
                lines = []
                for k, v in contacts.items():
                    if v: lines.append(f"<b>{k.capitalize()}:</b> {v}")
                contact_text = "\n".join(lines)
                await callback.message.answer(Messages.EmployerSearch.CONTACTS_GRANTED.format(contacts=contact_text))
            else:
                await callback.message.answer("✅ Доступ открыт, но кандидат не заполнил контакты.")
        elif response and response.get("notification_info"):
            info = response["notification_info"]
            cand_tg_id = info["candidate_telegram_id"]
            company = info["employer_company"]
            req_id = info["request_id"]
            
            try:
                await callback.bot.send_message(
                    chat_id=cand_tg_id,
                    text=f"🔔 <b>Вами заинтересовались!</b>\n\nКомпания <b>{company}</b> хочет получить доступ к вашим контактам.",
                    reply_markup=inline.get_notification_keyboard(req_id)
                )
                await callback.message.answer("✉️ Запрос отправлен кандидату в личные сообщения.")
            except Exception as e:
                logger.error(f"Failed to send notification to {cand_tg_id}: {e}")
                await callback.message.answer("⚠️ Не удалось отправить уведомление кандидату (возможно, он заблокировал бота).")
        
        else:
            await callback.message.answer(Messages.EmployerSearch.CONTACTS_DENIED)

    except Exception as e:
        logger.error(f"Contact request error: {e}")
        await callback.message.answer(Messages.EmployerSearch.CONTACTS_ERROR)

@router.callback_query(inline.SearchResultAction.filter(F.action == "get_resume"), EmployerSearch.showing_results)
async def handle_get_resume(callback: CallbackQuery, callback_data: inline.SearchResultAction, state: FSMContext) -> None:
    await callback.answer("Запрашиваю ссылку...")
    candidate_id = callback_data.candidate_id
    data = await state.get_data()
    candidate = data.get('current_candidate')
    
    if not candidate or str(candidate['id']) != candidate_id:
        candidate = await api_client.candidate_api_client.get_candidate(candidate_id)

    if not candidate or not candidate.get("resumes"):
         await callback.message.answer(Messages.EmployerSearch.RESUME_NONE); return

    file_id = candidate["resumes"][0]["file_id"]
    try:
        link = await api_client.file_api_client.get_download_url_by_file_id(file_id)
        if link:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 Скачать файл", url=link)]])
            await callback.message.answer(Messages.EmployerSearch.RESUME_LINK, reply_markup=keyboard)
        else:
            await callback.message.answer(Messages.EmployerSearch.RESUME_ERROR)
    except Exception:
        await callback.message.answer(Messages.EmployerSearch.RESUME_ERROR)

@router.message(Command("cancel"), StateFilter(EmployerSearch))
async def cancel_search_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(Messages.Common.CANCELLED, reply_markup=ReplyKeyboardRemove())

@router.message(StateFilter(EmployerSearch))
async def invalid_search_input_fallback(message: Message, state: FSMContext) -> None:
    await message.answer(Messages.Common.INVALID_INPUT)

@router.callback_query(F.data == "restart_search")
async def handle_restart_search(callback: CallbackQuery, state: FSMContext):
    await cmd_search(callback.message, state)
    await callback.answer()
