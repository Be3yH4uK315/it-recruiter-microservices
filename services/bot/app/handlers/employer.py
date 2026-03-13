import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    ReplyKeyboardRemove,
)

from app.core.messages import Messages
from app.keyboards import inline
from app.services import api_client
from app.states.employer import EmployerSearch
from app.utils import formatters, validators

router = Router()
logger = logging.getLogger(__name__)


async def show_next_candidate(message: Message | CallbackQuery, state: FSMContext) -> None:
    """
    Запрашивает следующего кандидата у бэкенда и отображает его.
    """
    data: dict[str, Any] = await state.get_data()
    session_id = data.get("session_id")
    target_message = message.message if isinstance(message, CallbackQuery) else message
    user_id = target_message.chat.id
    is_callback = isinstance(message, CallbackQuery)

    if not session_id:
        await target_message.answer(Messages.EmployerSearch.SESSION_EXPIRED)
        if is_callback:
            await message.answer()
        await state.clear()
        return

    try:
        candidate = await api_client.employer_api_client.get_next_candidate(session_id)

        if not candidate:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔄 Изменить фильтры", callback_data="restart_search"
                        )
                    ]
                ]
            )
            await target_message.answer(Messages.EmployerSearch.NO_MORE, reply_markup=keyboard)

            if is_callback:
                await message.answer()
            await state.clear()
            return

    except (api_client.APINetworkError, api_client.APIHTTPError) as e:
        logger.error(f"Error fetching next candidate for user {user_id}: {e}")
        await target_message.answer(Messages.Common.API_ERROR)
        if is_callback:
            await message.answer()
        return
    await state.update_data(current_candidate=candidate)

    candidate_id = str(candidate["id"])

    avatar_url: str | None = None
    if candidate.get("avatars") and candidate["avatars"]:
        avatar_file_id = candidate["avatars"][0].get("file_id")
        if avatar_file_id:
            try:
                avatar_url = await api_client.file_api_client.get_download_url_by_file_id(
                    avatar_file_id
                )
            except Exception:
                pass

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
                    await target_message.delete()
                    await target_message.answer_photo(
                        photo=avatar_url, caption=caption, reply_markup=keyboard
                    )
            else:
                await target_message.answer_photo(
                    photo=avatar_url, caption=caption, reply_markup=keyboard
                )
        else:
            if is_callback:
                if current_message_is_photo:
                    await target_message.delete()
                    await target_message.answer(text=caption, reply_markup=keyboard)
                else:
                    await target_message.edit_text(text=caption, reply_markup=keyboard)
            else:
                await target_message.answer(text=caption, reply_markup=keyboard)

    except Exception as e:
        logger.error(
            f"Error displaying candidate profile media for user {user_id}: {e}",
            exc_info=True,
        )
        try:
            await target_message.answer(text=caption, reply_markup=keyboard)
            if is_callback and current_message_is_photo:
                await target_message.delete()
        except Exception:
            pass

    if is_callback:
        await message.answer()


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext) -> None:
    """Обработка команды /search."""
    await state.clear()
    logger.info(f"User {message.from_user.id} started search")
    await state.update_data(filter_step="role", filters={})
    await state.set_state(EmployerSearch.entering_filters)
    await message.answer(Messages.EmployerSearch.STEP_1)


@router.message(EmployerSearch.entering_filters)
async def handle_filter_input(message: Message, state: FSMContext) -> None:
    data: dict[str, Any] = await state.get_data()
    filter_step: str | None = data.get("filter_step")
    filters: dict[str, Any] = data.get("filters", {})
    user_id = message.from_user.id

    if filter_step is None:
        await message.answer(Messages.Common.INVALID_INPUT)
        return

    try:
        next_step = None
        prompt = None
        input_text = message.text.strip() if message.text else ""
        keyboard = None

        if filter_step == "role":
            if not input_text:
                raise ValueError("Role empty")
            filters["role"] = input_text
            filters["must_skills"] = []
            prompt = Messages.EmployerSearch.STEP_2
            next_step = "must_skill_name"

        elif filter_step == "must_skill_name":
            if input_text == "/skip" or input_text.lower() == "пропустить":
                filters["nice_skills"] = []
                prompt = Messages.EmployerSearch.STEP_3
                next_step = "nice_skill_name"
            else:
                filters["current_skill"] = input_text
                prompt = Messages.EmployerSearch.SKILL_LEVEL_MUST.format(skill=input_text)
                keyboard = inline.get_skill_level_keyboard()
                next_step = "must_skill_level"

        elif filter_step == "nice_skill_name":
            if input_text == "/skip" or input_text.lower() == "пропустить":
                prompt = Messages.EmployerSearch.STEP_4
                next_step = "experience"
            else:
                filters["current_skill"] = input_text
                prompt = Messages.EmployerSearch.SKILL_LEVEL_NICE.format(skill=input_text)
                keyboard = inline.get_skill_level_keyboard()
                next_step = "nice_skill_level"

        elif filter_step == "experience":
            parts = input_text.replace(",", ".").split("-")
            try:
                exp_min = float(parts[0].strip())
                exp_max = float(parts[1].strip()) if len(parts) > 1 else None
                if exp_min < 0:
                    raise ValueError
                filters["experience_min"] = exp_min
                filters["experience_max"] = exp_max
            except ValueError:
                await message.answer(Messages.EmployerSearch.EXP_FORMAT_ERROR)
                return

            prompt = Messages.EmployerSearch.STEP_5
            next_step = "location"

        elif filter_step == "location":
            if input_text != "/skip":
                filters["location"] = input_text
            prompt = Messages.EmployerSearch.ENTER_ENGLISH
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
                    await message.answer(Messages.EmployerSearch.SALARY_PARSE_ERROR)
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
            await message.answer(
                Messages.EmployerSearch.USE_BUTTONS_WORK_MODE,
                reply_markup=inline.get_work_modes_keyboard(
                    selected=set(filters.get("work_modes", []))
                ),
            )
            return

        await state.update_data(filter_step=next_step, filters=filters)
        if prompt:
            await message.answer(prompt, reply_markup=keyboard)

    except ValueError:
        await message.answer(Messages.Common.INVALID_INPUT)
    except Exception as e:
        logger.error(f"Error filter input user {user_id}: {e}", exc_info=True)
        await message.answer(Messages.Common.API_ERROR)
        await state.clear()


@router.callback_query(inline.SkillLevelCallback.filter(), EmployerSearch.entering_filters)
async def handle_employer_skill_level(
    callback: CallbackQuery, callback_data: inline.SkillLevelCallback, state: FSMContext
) -> None:
    data = await state.get_data()
    filter_step = data.get("filter_step")

    if filter_step not in ["must_skill_level", "nice_skill_level"]:
        await callback.answer()
        return

    filters = data.get("filters", {})
    skill_name = filters.get("current_skill", "Навык")
    level = callback_data.level

    if filter_step == "must_skill_level":
        must_skills = filters.get("must_skills", [])
        must_skills.append({"skill": skill_name, "level": level})
        filters["must_skills"] = must_skills
        next_step = "must_skill_name"
        prompt = Messages.EmployerSearch.NEXT_MUST_SKILL
    else:
        nice_skills = filters.get("nice_skills", [])
        nice_skills.append({"skill": skill_name, "level": level})
        filters["nice_skills"] = nice_skills
        next_step = "nice_skill_name"
        prompt = Messages.EmployerSearch.NEXT_NICE_SKILL

    filters["current_skill"] = None
    await state.update_data(filters=filters, filter_step=next_step)

    try:
        await callback.message.edit_text(
            Messages.EmployerSearch.SKILL_ADDED.format(skill=skill_name, level=level)
        )
    except Exception:
        pass

    await callback.message.answer(prompt)
    await callback.answer()


@router.callback_query(inline.WorkModeCallback.filter(), EmployerSearch.entering_filters)
async def handle_employer_work_mode(
    callback: CallbackQuery, callback_data: inline.WorkModeCallback, state: FSMContext
) -> None:
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
        mode_str = ", ".join(readable_modes) if readable_modes else "Любой формат"
        final_text = Messages.EmployerSearch.WORK_MODES_SELECTED.format(modes=mode_str)

        try:
            await callback.message.edit_text(final_text)
        except Exception:
            pass

        def format_skills(s_list):
            if not s_list:
                return "Нет"
            return ", ".join(
                [
                    (
                        f"{s.get('skill', '')} ({s.get('level', '')})"
                        if isinstance(s, dict)
                        else str(s)
                    )
                    for s in s_list
                ]
            )

        exp_str = (
            f"• Опыт: от {filters['experience_min']} лет\n" if filters.get("experience_min") else ""
        )
        salary_str = (
            f"• Бюджет: до {filters['salary_max']} {filters.get('currency','RUB')}\n"
            if filters.get("salary_max")
            else ""
        )
        mode_res_str = f"• Формат: {', '.join(readable_modes)}\n" if readable_modes else ""

        summary = Messages.EmployerSearch.SEARCH_SUMMARY.format(
            role=filters.get("role"),
            must_skills=format_skills(filters.get("must_skills")),
            nice_skills=format_skills(filters.get("nice_skills")),
            exp=exp_str,
            salary=salary_str,
            modes=mode_res_str,
        )

        await callback.message.answer(summary)
        await callback.message.answer(Messages.EmployerSearch.SAVING)

        user_id = callback.from_user.id
        employer_profile = data.get("employer_profile")
        if not employer_profile:
            employer_profile = await api_client.employer_api_client.get_or_create_employer(
                user_id, callback.from_user.username or "HR"
            )
            await state.update_data(employer_profile=employer_profile)

        if not employer_profile:
            await callback.message.answer(Messages.EmployerSearch.EMPLOYER_ERROR)
            await state.clear()
            return

        search_session = await api_client.employer_api_client.create_search_session(
            employer_profile["id"], filters
        )

        if not search_session:
            await callback.message.answer(Messages.EmployerSearch.SEARCH_ERROR)
            await state.clear()
            return

        await state.update_data(session_id=search_session["id"])
        await state.set_state(EmployerSearch.showing_results)
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
        mode_str = ", ".join(readable_modes) if readable_modes else "Любой формат"
        current_selection_text = f"\n\n👉 <b>Текущий выбор:</b> {mode_str}"
        try:
            await callback.message.edit_text(
                Messages.EmployerSearch.STEP_6 + current_selection_text,
                reply_markup=inline.get_work_modes_keyboard(selected=selected_modes),
            )
        except Exception:
            pass
    await callback.answer()


@router.callback_query(inline.EnglishLevelCallback.filter(), EmployerSearch.entering_filters)
async def handle_employer_english_level(
    callback: CallbackQuery,
    callback_data: inline.EnglishLevelCallback,
    state: FSMContext,
) -> None:
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
        await callback.message.edit_text(
            Messages.EmployerSearch.ENGLISH_LEVEL_SELECTED.format(level=text_level)
        )
    except Exception:
        pass

    await callback.message.answer(Messages.EmployerSearch.ENTER_SALARY)
    await callback.answer()


@router.callback_query(inline.SearchResultDecision.filter(), EmployerSearch.showing_results)
async def handle_decision(
    callback: CallbackQuery,
    callback_data: inline.SearchResultDecision,
    state: FSMContext,
) -> None:
    data: dict[str, Any] = await state.get_data()
    session_id: str | None = data.get("session_id")

    if not session_id:
        await callback.answer(Messages.EmployerSearch.SESSION_EXPIRED, show_alert=True)
        return

    try:
        success = await api_client.employer_api_client.save_decision(
            session_id=session_id,
            candidate_id=callback_data.candidate_id,
            decision=callback_data.action,
        )
        if not success:
            await callback.answer(Messages.EmployerSearch.DECISION_ERROR, show_alert=True)
            return

        if callback_data.action == "like":
            await callback.answer(Messages.EmployerSearch.DECISION_LIKE)
            data = await state.get_data()
            cand = data.get("current_candidate", {})
            visibility = cand.get("contacts_visibility", "on_request")

            new_keyboard = inline.get_liked_candidate_keyboard(
                callback_data.candidate_id, visibility
            )
            await callback.message.edit_reply_markup(reply_markup=new_keyboard)
        else:
            await callback.answer(Messages.EmployerSearch.CANDIDATE_HIDDEN)
            await show_next_candidate(callback, state)

    except Exception as e:
        logger.error(f"Error saving decision: {e}")
        await callback.answer(Messages.EmployerSearch.DECISION_ERROR, show_alert=True)


@router.callback_query(
    inline.SearchResultAction.filter(F.action == "next"), EmployerSearch.showing_results
)
async def handle_next_candidate(
    callback: CallbackQuery, callback_data: inline.SearchResultAction, state: FSMContext
) -> None:
    data: dict[str, Any] = await state.get_data()
    session_id: str | None = data.get("session_id")
    current_candidate = data.get("current_candidate")

    if not session_id or not current_candidate:
        await callback.answer(Messages.EmployerSearch.SESSION_ERROR_ALERT, show_alert=True)
        return

    try:
        await api_client.employer_api_client.save_decision(
            session_id=session_id, candidate_id=current_candidate["id"], decision="skip"
        )
    except Exception as e:
        logger.error(f"Failed to save skip decision: {e}")

    await callback.answer()
    await show_next_candidate(callback, state)


@router.callback_query(
    inline.SearchResultAction.filter(F.action == "contact"),
    EmployerSearch.showing_results,
)
async def handle_show_contact(
    callback: CallbackQuery, callback_data: inline.SearchResultAction, state: FSMContext
) -> None:
    data = await state.get_data()
    employer_profile = data.get("employer_profile")

    if not employer_profile:
        employer_profile = await api_client.employer_api_client.get_or_create_employer(
            callback.from_user.id, callback.from_user.username or "HR"
        )
        if employer_profile:
            await state.update_data(employer_profile=employer_profile)
        else:
            await callback.answer(Messages.EmployerSearch.SESSION_ERROR_ALERT, show_alert=True)
            return

    candidate_id = callback_data.candidate_id
    await callback.answer(Messages.EmployerSearch.CONTACTS_REQUEST, show_alert=False)

    try:
        response = await api_client.employer_api_client.request_contacts(
            employer_id=employer_profile["id"], candidate_id=candidate_id
        )

        if response and response.get("granted"):
            contacts = response.get("contacts")
            if contacts:
                lines = [f"<b>{k.capitalize()}:</b> {v}" for k, v in contacts.items() if v]
                await callback.message.answer(
                    Messages.EmployerSearch.CONTACTS_GRANTED.format(contacts="\n".join(lines))
                )
            else:
                await callback.message.answer(Messages.EmployerSearch.CONTACTS_EMPTY)
        elif response and response.get("notification_info"):
            info = response["notification_info"]
            try:
                msg_text = Messages.Notifications.CANDIDATE_CONTACT_REQUEST.format(
                    company=info["employer_company"]
                )
                await callback.bot.send_message(
                    chat_id=info["candidate_telegram_id"],
                    text=msg_text,
                    reply_markup=inline.get_notification_keyboard(info["request_id"]),
                )
                await callback.message.answer(Messages.EmployerSearch.NOTIFY_SENT)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
                await callback.message.answer(Messages.EmployerSearch.NOTIFY_ERROR)
        else:
            await callback.message.answer(Messages.EmployerSearch.CONTACTS_DENIED)

    except Exception as e:
        logger.error(f"Contact request error: {e}")
        await callback.message.answer(Messages.EmployerSearch.CONTACTS_ERROR)


@router.callback_query(
    inline.SearchResultAction.filter(F.action == "get_resume"),
    EmployerSearch.showing_results,
)
async def handle_get_resume(
    callback: CallbackQuery, callback_data: inline.SearchResultAction, state: FSMContext
) -> None:
    await callback.answer(Messages.EmployerSearch.FETCHING_LINK)
    candidate_id = callback_data.candidate_id
    data = await state.get_data()
    candidate = data.get("current_candidate")

    if not candidate or str(candidate["id"]) != candidate_id:
        candidate = await api_client.candidate_api_client.get_candidate(candidate_id)

    if not candidate or not candidate.get("resumes"):
        await callback.message.answer(Messages.EmployerSearch.RESUME_NONE)
        return

    file_id = candidate["resumes"][0]["file_id"]
    try:
        link = await api_client.file_api_client.get_download_url_by_file_id(file_id)
        if link:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="📥 Скачать файл", url=link)]]
            )
            await callback.message.answer(
                Messages.EmployerSearch.RESUME_LINK, reply_markup=keyboard
            )
        else:
            await callback.message.answer(Messages.EmployerSearch.RESUME_ERROR)
    except Exception:
        await callback.message.answer(Messages.EmployerSearch.RESUME_ERROR)


async def show_list_candidate(callback: CallbackQuery, state: FSMContext, index: int):
    """Отображает кандидата из списка (Избранное или Контакты) с пагинацией."""
    data = await state.get_data()
    candidates = data.get("candidate_list", [])
    list_type = data.get("list_type", "favorites")

    if not candidates or index >= len(candidates) or index < 0:
        return

    candidate = candidates[index]

    avatar_url = None
    if candidate.get("avatars") and candidate["avatars"]:
        avatar_file_id = candidate["avatars"][0].get("file_id")
        if avatar_file_id:
            try:
                avatar_url = await api_client.file_api_client.get_download_url_by_file_id(
                    avatar_file_id
                )
            except Exception:
                pass

    header = Messages.EmployerMenu.LIST_HEADER.format(current=index + 1, total=len(candidates))
    caption = f"<b>{header}</b>\n\n" + formatters.format_candidate_profile(
        candidate, is_owner=False
    )

    if list_type == "contacts" and candidate.get("contacts"):
        lines = [f"<b>{k.capitalize()}:</b> {v}" for k, v in candidate["contacts"].items() if v]
        caption += "\n\n<b>✅ Открытые контакты:</b>\n" + "\n".join(lines)

    has_resume = bool(candidate.get("resumes"))
    keyboard = inline.get_employer_list_keyboard(index, len(candidates), list_type, has_resume)

    try:
        if avatar_url:
            media = InputMediaPhoto(media=avatar_url, caption=caption)
            if callback.message.photo:
                await callback.message.edit_media(media=media, reply_markup=keyboard)
            else:
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=avatar_url, caption=caption, reply_markup=keyboard
                )
        else:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(text=caption, reply_markup=keyboard)
            else:
                await callback.message.edit_text(text=caption, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error displaying list candidate: {e}")


@router.callback_query(inline.EmployerMenuAction.filter())
async def handle_employer_menu(
    callback: CallbackQuery, callback_data: inline.EmployerMenuAction, state: FSMContext
):
    action = callback_data.action
    data = await state.get_data()
    employer_profile = data.get("employer_profile")
    emp_id = employer_profile["id"]

    if action == "new_search":
        await state.update_data(filter_step="role", filters={})
        await state.set_state(EmployerSearch.entering_filters)
        await callback.message.edit_text(Messages.EmployerSearch.STEP_1)

    elif action == "favorites":
        await callback.answer(Messages.EmployerMenu.UPLOADING_FAVORITES)
        favorites = await api_client.employer_api_client.get_favorites(emp_id)
        if not favorites:
            await callback.message.edit_text(
                Messages.EmployerMenu.FAVORITES_EMPTY, reply_markup=inline.get_employer_main_menu()
            )
            return
        await state.update_data(candidate_list=favorites, list_type="favorites")
        await state.set_state(EmployerSearch.viewing_list)
        await show_list_candidate(callback, state, 0)

    elif action == "contacts":
        await callback.answer(Messages.EmployerMenu.UPLOADING_CONTACTS)
        contacts = await api_client.employer_api_client.get_unlocked_contacts(emp_id)
        if not contacts:
            await callback.message.edit_text(
                Messages.EmployerMenu.CONTACTS_EMPTY, reply_markup=inline.get_employer_main_menu()
            )
            return
        await state.update_data(candidate_list=contacts, list_type="contacts")
        await state.set_state(EmployerSearch.viewing_list)
        await show_list_candidate(callback, state, 0)

    elif action == "main":
        await state.set_state(EmployerSearch.main_menu)
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                Messages.EmployerMenu.MAIN_MENU, reply_markup=inline.get_employer_main_menu()
            )
        else:
            await callback.message.edit_text(
                Messages.EmployerMenu.MAIN_MENU, reply_markup=inline.get_employer_main_menu()
            )

    elif action == "stats":
        await callback.answer(Messages.EmployerMenu.LOADING_STATS)
        stats = await api_client.employer_api_client.get_statistics(emp_id)

        view = stats.get("total_viewed", 0)
        like = stats.get("total_liked", 0)
        req = stats.get("total_contact_requests", 0)
        grant = stats.get("total_contacts_granted", 0)

        liked_perc = f"({int(like/view * 100)}%)" if view > 0 else ""
        granted_perc = f"({int(grant/req * 100)}%)" if req > 0 else ""

        text = Messages.EmployerMenu.STATS_TEMPLATE.format(
            viewed=view,
            liked=like,
            liked_perc=liked_perc,
            reqs=req,
            granted=grant,
            granted_perc=granted_perc,
        )
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=inline.get_employer_main_menu())
        else:
            await callback.message.edit_text(text, reply_markup=inline.get_employer_main_menu())

    elif action == "history":
        await callback.answer(Messages.EmployerMenu.LOADING_SESSIONS)
        sessions = await api_client.employer_api_client.get_searches(emp_id)
        if not sessions:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    Messages.EmployerMenu.SESSIONS_EMPTY,
                    reply_markup=inline.get_employer_main_menu(),
                )
            else:
                await callback.message.edit_text(
                    Messages.EmployerMenu.SESSIONS_EMPTY,
                    reply_markup=inline.get_employer_main_menu(),
                )
            return

        text = Messages.EmployerMenu.SESSIONS_HEADER
        kb = inline.get_sessions_keyboard(sessions)
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)

    await callback.answer()


@router.callback_query(inline.EmployerListAction.filter(), EmployerSearch.viewing_list)
async def handle_list_pagination(
    callback: CallbackQuery, callback_data: inline.EmployerListAction, state: FSMContext
):
    action = callback_data.action
    index = callback_data.index

    if action in ["prev", "next"]:
        await show_list_candidate(callback, state, index)
        await callback.answer()

    elif action == "get_resume":
        await callback.answer(Messages.EmployerSearch.FETCHING_LINK)
        try:
            data = await state.get_data()
            cand = data["candidate_list"][index]
            file_id = cand["resumes"][0]["file_id"]
            link = await api_client.file_api_client.get_download_url_by_file_id(file_id)
            if link:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="📥 Скачать файл", url=link)]]
                )
                await callback.message.answer(Messages.EmployerSearch.RESUME_LINK, reply_markup=kb)
            else:
                await callback.message.answer(Messages.EmployerSearch.RESUME_ERROR)
        except Exception:
            await callback.message.answer(Messages.EmployerSearch.RESUME_ERROR)


@router.callback_query(inline.EmployerSessionAction.filter(), EmployerSearch.main_menu)
async def handle_resume_session(
    callback: CallbackQuery, callback_data: inline.EmployerSessionAction, state: FSMContext
):
    """Продолжить предыдущий поиск."""
    session_id = callback_data.session_id

    await callback.answer(Messages.EmployerSearch.SAVING)

    await state.update_data(session_id=session_id)
    await state.set_state(EmployerSearch.showing_results)

    await show_next_candidate(callback, state)


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
