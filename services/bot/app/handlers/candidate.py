import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from app.core.messages import Messages
from app.keyboards import inline
from app.services import api_client
from app.states.candidate import CandidateFSM
from app.utils import formatters, processors, validators

router = Router()
logger = logging.getLogger(__name__)


class CandidateData(TypedDict, total=False):
    mode: str
    field_to_edit: str | None
    current_field: str | None
    block_type: str | None
    current_step: str | None
    action_type: str | None
    file_type: str | None
    display_name: str | None
    headline_role: str | None
    location: str | None
    work_modes: list[str]
    contacts: dict[str, Any] | None
    contacts_visibility: str | None
    experiences: list[dict[str, Any]]
    new_experiences: list[dict[str, Any]]
    skills: list[dict[str, Any]]
    new_skills: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    new_projects: list[dict[str, Any]]
    education: list[dict[str, Any]]
    new_education: list[dict[str, Any]]
    current_edu_level: str | None
    current_edu_inst: str | None
    current_exp_company: str | None
    current_exp_position: str | None
    current_exp_start_date: str | None
    current_exp_end_date: str | None
    current_skill_name: str | None
    current_skill_kind: str | None
    current_project_title: str | None
    current_project_description: str | None
    profile_cache: dict[str, Any] | None


async def _process_file_upload(
    message: Message,
    telegram_id: int,
    file_type: str,
    validation_rules: dict,
    replace_api_call: Callable[[int, str], Awaitable[bool]],
) -> bool:
    try:
        file_obj = None
        filename = "unknown"
        mime_type = "application/octet-stream"
        file_size = 0

        if file_type == "resume":
            if not message.document:
                await message.answer(Messages.Common.INVALID_INPUT)
                return False
            file_obj = message.document
            filename = file_obj.file_name or f"resume_{telegram_id}.pdf"
            mime_type = file_obj.mime_type or "application/pdf"
            file_size = file_obj.file_size

        elif file_type == "avatar":
            if not message.photo:
                await message.answer(Messages.Common.INVALID_INPUT)
                return False
            file_obj = message.photo[-1]
            file_info_meta = await message.bot.get_file(file_obj.file_id)
            extension = (
                file_info_meta.file_path.split(".")[-1].lower()
                if "." in file_info_meta.file_path
                else "jpg"
            )
            filename = f"avatar_{telegram_id}.{extension}"
            mime_type = f"image/{extension}"
            file_size = file_obj.file_size
        else:
            return False

        if file_size > validation_rules["max_size"]:
            await message.answer(validation_rules["too_big_msg"])
            return False

        await message.answer(validation_rules["processing_msg"])
        file_info = await message.bot.get_file(file_obj.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
        file_bytes = downloaded_file.read()

        old_file_id = None
        try:
            candidate_profile = await api_client.candidate_api_client.get_candidate_by_telegram_id(
                telegram_id
            )
            if candidate_profile:
                relation_key = f"{file_type}s"
                if candidate_profile.get(relation_key) and candidate_profile[relation_key]:
                    old_file_id = candidate_profile[relation_key][0].get("file_id")
        except Exception:
            pass

        file_response = await api_client.file_api_client.upload_file(
            filename=filename,
            file_data=file_bytes,
            content_type=mime_type,
            owner_id=telegram_id,
            file_type=file_type,
        )
        if not file_response:
            await message.answer(validation_rules["update_error_msg"])
            return False

        success = await replace_api_call(telegram_id, file_response["id"])
        if not success:
            await message.answer(validation_rules["update_error_msg"])
            return False

        if old_file_id:
            asyncio.create_task(
                api_client.file_api_client.delete_file(old_file_id, owner_telegram_id=telegram_id)
            )

        await message.answer(validation_rules["updated_msg"])
        return True
    except Exception as e:
        logger.error(f"Error _process_file_upload: {e}")
        await message.answer(validation_rules["update_error_msg"])
        return False


async def _process_resume_upload(message: Message, telegram_id: int) -> bool:
    rules = {
        "mime_types": [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        "max_size": 10 * 1024 * 1024,
        "wrong_type_msg": Messages.Profile.RESUME_WRONG_TYPE,
        "too_big_msg": Messages.Profile.RESUME_TOO_BIG,
        "processing_msg": Messages.Profile.RESUME_PROCESSING,
        "update_error_msg": Messages.Profile.RESUME_UPDATE_ERROR,
        "updated_msg": Messages.Profile.RESUME_UPDATED,
    }
    return await _process_file_upload(
        message,
        telegram_id,
        "resume",
        rules,
        api_client.candidate_api_client.replace_resume,
    )


async def _process_avatar_upload(message: Message, telegram_id: int) -> bool:
    rules = {
        "mime_types": ["image/jpeg", "image/png"],
        "max_size": 5 * 1024 * 1024,
        "wrong_type_msg": Messages.Profile.AVATAR_FORMAT_ERROR,
        "too_big_msg": "❌ Аватар слишком большой (макс. 5 МБ).",
        "processing_msg": Messages.Profile.AVATAR_PROCESSING,
        "update_error_msg": Messages.Profile.AVATAR_UPDATE_ERROR,
        "updated_msg": Messages.Profile.AVATAR_UPDATED,
    }
    return await _process_file_upload(
        message,
        telegram_id,
        "avatar",
        rules,
        api_client.candidate_api_client.replace_avatar,
    )


@router.callback_query(inline.ContactsVisibilityCallback.filter(), CandidateFSM.selecting_options)
async def _process_contacts_visibility(
    callback: CallbackQuery,
    callback_data: inline.ContactsVisibilityCallback,
    state: FSMContext,
):
    data: CandidateData = await state.get_data()
    mode: str = data.get("mode", "register")
    user_id = callback.from_user.id

    try:
        await state.update_data(contacts_visibility=callback_data.visibility)
        await callback.message.edit_text(
            f"✅ Видимость контактов установлена: {callback_data.visibility}"
        )

        if mode == "edit":
            payload = {"contacts_visibility": callback_data.visibility}
            if "contacts" in data and data["contacts"] is not None:
                payload["contacts"] = data.get("contacts")

            updated_profile = await api_client.candidate_api_client.update_candidate_profile(
                user_id, payload
            )
            if updated_profile:
                await callback.message.answer(Messages.Profile.CONTACTS_UPDATED)
                await state.update_data(profile_cache=updated_profile)
            else:
                await callback.message.answer(Messages.Profile.CONTACTS_UPDATE_ERROR)

            await state.clear()
            await _show_profile(callback, state)
        else:
            await _ask_for_resume(callback.message, state)

    except Exception as e:
        logger.error(f"Error _process_contacts_visibility: {e}")
        await callback.message.answer(Messages.Common.API_ERROR)
        await state.clear()
    finally:
        await callback.answer()


async def _show_profile(target: Message | CallbackQuery, state: FSMContext) -> None:
    target_message = target if isinstance(target, Message) else target.message
    user_id: int = target_message.chat.id
    is_callback = isinstance(target, CallbackQuery)

    data: CandidateData = await state.get_data()
    profile: dict[str, Any] | None = data.get("profile_cache")
    if profile:
        await state.update_data(profile_cache=None)
    else:
        try:
            profile = await api_client.candidate_api_client.get_candidate_by_telegram_id(user_id)
            if not profile:
                await target_message.answer(Messages.Profile.NOT_FOUND)
                if is_callback:
                    await target.answer()
                return
            await state.update_data(profile_cache=profile)
        except Exception:
            await target_message.answer(Messages.Common.API_ERROR)
            if is_callback:
                await target.answer()
            return

    avatar_url: str | None = None
    if profile.get("avatars") and profile["avatars"]:
        avatar_file_id = profile["avatars"][0].get("file_id")
        if avatar_file_id:
            try:
                avatar_url = await api_client.file_api_client.get_download_url_by_file_id(
                    avatar_file_id
                )
            except Exception:
                pass

    caption = formatters.format_candidate_profile(profile, is_owner=True)
    has_avatar = bool(avatar_url)
    has_resume = bool(profile.get("resumes"))
    is_hidden = profile.get("status") == "hidden"
    keyboard = inline.get_profile_actions_keyboard(
        has_avatar=has_avatar, has_resume=has_resume, is_hidden=is_hidden
    )
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
    except Exception:
        try:
            await target_message.answer(text=caption, reply_markup=keyboard)
            if is_callback and current_message_is_photo:
                await target_message.delete()
        except Exception:
            pass

    if is_callback:
        await target.answer()
    await state.set_state(CandidateFSM.showing_profile)


async def _ask_for_education(message: Message, state: FSMContext) -> None:
    await state.update_data(education=[])
    await message.answer(
        Messages.Profile.ENTER_EDUCATION,
        reply_markup=inline.get_confirmation_keyboard("edu"),
    )
    await state.update_data(action_type="start_adding_edu")
    await state.set_state(CandidateFSM.confirm_action)


async def _ask_for_experience(message: Message, state: FSMContext) -> None:
    await state.update_data(experiences=[])
    await message.answer(
        Messages.Profile.ENTER_EXPERIENCE,
        reply_markup=inline.get_confirmation_keyboard("exp"),
    )
    await state.update_data(action_type="start_adding_experience")
    await state.set_state(CandidateFSM.confirm_action)


async def _ask_for_skills(message: Message, state: FSMContext) -> None:
    await state.update_data(skills=[])
    await message.answer(Messages.Profile.ENTER_SKILL_NAME)
    await state.update_data(block_type="skill", current_step="name")
    await state.set_state(CandidateFSM.block_entry)


async def _ask_for_projects(message: Message, state: FSMContext) -> None:
    await state.update_data(projects=[])
    await message.answer(
        Messages.Profile.ENTER_PROJECT,
        reply_markup=inline.get_confirmation_keyboard("project"),
    )
    await state.update_data(action_type="start_adding_project")
    await state.set_state(CandidateFSM.confirm_action)


async def _ask_for_location(message: Message, state: FSMContext) -> None:
    await message.answer(Messages.Profile.ENTER_LOCATION)
    await state.update_data(current_field="location")
    await state.set_state(CandidateFSM.entering_basic_info)


async def _ask_for_contacts(message: Message, state: FSMContext) -> None:
    await message.answer(Messages.Profile.ENTER_CONTACTS)
    await state.set_state(CandidateFSM.editing_contacts)


async def _ask_for_english(target: Message | CallbackQuery, state: FSMContext) -> None:
    msg = target if isinstance(target, Message) else target.message
    await state.update_data(current_field="english_level")
    await state.set_state(CandidateFSM.selecting_options)
    await msg.answer(
        Messages.Profile.ENTER_ENGLISH, reply_markup=inline.get_english_level_keyboard()
    )


async def _ask_for_about_me(target: Message | CallbackQuery, state: FSMContext) -> None:
    msg = target if isinstance(target, Message) else target.message
    await state.update_data(current_field="about_me")
    await state.set_state(CandidateFSM.entering_basic_info)
    await msg.answer(Messages.Profile.ENTER_ABOUT_ME)


async def _ask_for_resume(message: Message, state: FSMContext) -> None:
    data: CandidateData = await state.get_data()
    mode: str = data.get("mode", "register")
    user_id = message.chat.id
    user = message.from_user
    if mode == "register":
        user_contacts = data.get("contacts") or {}
        if user.username and "telegram" not in user_contacts:
            user_contacts["telegram"] = f"@{user.username}"
        try:
            payload = {
                "telegram_id": user_id,
                "display_name": data.get("display_name"),
                "headline_role": data.get("headline_role"),
                "education": data.get("education", []),
                "experiences": data.get("experiences", []),
                "skills": data.get("skills", []),
                "projects": data.get("projects", []),
                "location": data.get("location"),
                "work_modes": data.get("work_modes", []),
                "contacts": user_contacts,
                "contacts_visibility": data.get("contacts_visibility", "hidden"),
                "salary_min": data.get("salary_min"),
                "salary_max": data.get("salary_max"),
                "currency": data.get("currency", "RUB"),
                "experience_years": 0,
                "english_level": data.get("english_level"),
                "about_me": data.get("about_me"),
            }
            created_profile = await api_client.candidate_api_client.register_candidate_profile(
                payload
            )
            if not created_profile:
                await message.answer(Messages.Profile.FINISH_ERROR)
                await state.clear()
                return
            await state.update_data(profile_cache=created_profile)
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            await message.answer(Messages.Profile.FINISH_ERROR)
            await state.clear()
            return

    await message.answer(Messages.Profile.UPLOAD_RESUME)
    await state.update_data(file_type="resume")
    await state.set_state(CandidateFSM.uploading_file)


async def _ask_for_avatar(message: Message, state: FSMContext) -> None:
    await message.answer(Messages.Profile.UPLOAD_AVATAR)
    await state.update_data(file_type="avatar")
    await state.set_state(CandidateFSM.uploading_file)


async def _finish_registration_or_edit(message: Message, state: FSMContext) -> None:
    data: CandidateData = await state.get_data()
    mode: str = data.get("mode", "register")
    telegram_id: int = message.from_user.id
    try:
        if mode == "register":
            await message.answer(Messages.Profile.FINISH_OK)
        elif mode == "edit":
            field_to_edit = data.get("field_to_edit")
            edit_payload = {}
            if field_to_edit in ["display_name", "headline_role", "location"]:
                edit_payload = {field_to_edit: data.get(field_to_edit)}
            elif "new_experiences" in data:
                edit_payload["experiences"] = data.get("new_experiences")
            elif "new_skills" in data:
                edit_payload["skills"] = data.get("new_skills")
            elif "new_projects" in data:
                edit_payload["projects"] = data.get("new_projects")

            if edit_payload:
                success = await api_client.candidate_api_client.update_candidate_profile(
                    telegram_id, edit_payload
                )
                await message.answer(
                    Messages.Profile.FIELD_UPDATED
                    if success
                    else Messages.Profile.FIELD_UPDATE_ERROR
                )
    except api_client.APIHTTPError as e:
        if mode == "register" and e.status_code == 409:
            await message.answer(Messages.Profile.ALREADY_REGISTERED)
        else:
            await message.answer(Messages.Common.API_ERROR)
    except Exception:
        await message.answer(Messages.Profile.FINISH_ERROR)
    finally:
        await state.clear()
        await _show_profile(message, state)


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(mode="edit")
    await _show_profile(message, state)


@router.callback_query(inline.ProfileAction.filter(), CandidateFSM.showing_profile)
async def handle_profile_action(
    callback: CallbackQuery, callback_data: inline.ProfileAction, state: FSMContext
) -> None:
    await state.update_data(mode="edit")
    action = callback_data.action
    user_id = callback.from_user.id

    if action == "edit":
        await state.set_state(CandidateFSM.choosing_field)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            Messages.Profile.CHOOSE_FIELD,
            reply_markup=inline.get_profile_edit_keyboard(),
        )
        await callback.answer()
        return

    elif action == "upload_resume":
        await state.update_data(file_type="resume")
        await state.set_state(CandidateFSM.uploading_file)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_RESUME)
    elif action == "upload_avatar":
        await state.update_data(file_type="avatar")
        await state.set_state(CandidateFSM.uploading_file)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_AVATAR)
    elif action == "delete_avatar":
        try:
            success = await api_client.candidate_api_client.delete_avatar(user_id)
            await callback.answer(
                Messages.Profile.DELETE_AVATAR_OK
                if success
                else Messages.Profile.DELETE_AVATAR_ERROR
            )
            await state.update_data(profile_cache=None)
            await _show_profile(callback, state)
        except Exception:
            await callback.message.answer(Messages.Common.API_ERROR)
    elif action == "delete_resume":
        try:
            success = await api_client.candidate_api_client.delete_resume(user_id)
            await callback.answer(
                Messages.Profile.DELETE_RESUME_OK
                if success
                else Messages.Profile.DELETE_RESUME_ERROR
            )
            await state.update_data(profile_cache=None)
            await _show_profile(callback, state)
        except Exception:
            await callback.message.answer(Messages.Common.API_ERROR)
    elif action == "download_my_resume":
        data = await state.get_data()
        profile = data.get("profile_cache")
        if not profile:
            profile = await api_client.candidate_api_client.get_candidate_by_telegram_id(user_id)
        if profile and profile.get("resumes"):
            try:
                link = await api_client.file_api_client.get_download_url_by_file_id(
                    profile["resumes"][0]["file_id"]
                )
                if link:
                    await callback.message.answer(
                        Messages.Profile.MY_RESUME_LINK.format(link=link),
                        disable_web_page_preview=True,
                    )
                else:
                    await callback.message.answer(Messages.Profile.LINK_ERROR)
            except Exception:
                await callback.message.answer(Messages.Profile.FILE_SERVICE_ERROR)
        else:
            await callback.message.answer(Messages.Profile.NO_RESUME_UPLOADED)
        await callback.answer()
    elif action in ["set_active", "set_hidden"]:
        new_status = "active" if action == "set_active" else "hidden"
        try:
            updated = await api_client.candidate_api_client.update_candidate_profile(
                user_id, {"status": new_status}
            )
            if updated:
                await callback.answer(
                    Messages.Profile.PROFILE_ACTIVATED
                    if new_status == "active"
                    else Messages.Profile.PROFILE_HIDDEN
                )
                await state.update_data(profile_cache=updated)
                await _show_profile(callback, state)
            else:
                await callback.answer(Messages.Profile.FIELD_UPDATE_ERROR, show_alert=True)
        except Exception:
            await callback.answer(Messages.Common.API_ERROR, show_alert=True)


@router.callback_query(
    inline.EditFieldCallback.filter(F.field_name != "back"), CandidateFSM.choosing_field
)
async def handle_field_chosen(
    callback: CallbackQuery, callback_data: inline.EditFieldCallback, state: FSMContext
) -> None:
    field: str = callback_data.field_name
    await state.update_data(field_to_edit=field)
    profile = (await state.get_data()).get("profile_cache") or {}
    try:
        await callback.message.delete()
    except Exception:
        pass

    prompts = {
        "display_name": Messages.Profile.ENTER_NAME,
        "headline_role": Messages.Profile.ENTER_ROLE,
        "location": Messages.Profile.ENTER_LOCATION,
        "about_me": Messages.Profile.ENTER_ABOUT_ME,
    }
    block_starts = {
        "experiences": (
            Messages.Profile.ENTER_EXPERIENCE_COMPANY,
            "experience",
            "company",
        ),
        "education": (Messages.Profile.ENTER_EDU_LEVEL, "education", "level"),
        "skills": (Messages.Profile.ENTER_SKILL_NAME, "skill", "name"),
        "projects": (Messages.Profile.ENTER_PROJECT_TITLE, "project", "title"),
    }

    if field in prompts:
        await state.update_data(current_field=field)
        await state.set_state(CandidateFSM.entering_basic_info)
        await callback.message.answer(prompts[field])
    elif field == "contacts":
        await state.update_data(contacts=profile.get("contacts"))
        await state.set_state(CandidateFSM.editing_contacts)
        await callback.message.answer(Messages.Profile.ENTER_CONTACTS)
    elif field in block_starts:
        prompt, block_type, current_step = block_starts[field]
        await state.update_data(
            block_type=block_type,
            current_step=current_step,
            **{f"new_{field}": profile.get(field, [])},
        )
        await state.set_state(CandidateFSM.block_entry)
        await callback.message.answer(prompt)
    elif field == "work_modes":
        current_modes = set(profile.get("work_modes", []))
        await state.update_data(work_modes=list(current_modes))
        await state.set_state(CandidateFSM.selecting_options)
        await callback.message.answer(
            Messages.Profile.WORK_MODE_SELECT,
            reply_markup=inline.get_work_modes_keyboard(selected=current_modes),
        )
    elif field == "contacts_visibility":
        await state.set_state(CandidateFSM.selecting_options)
        await callback.message.answer(
            Messages.Profile.CONTACTS_VISIBILITY_SELECT,
            reply_markup=inline.get_contacts_visibility_keyboard(),
        )
    elif field == "salary":
        await state.update_data(current_field="salary")
        await state.set_state(CandidateFSM.entering_basic_info)
        await callback.message.answer(Messages.Profile.ENTER_SALARY)
    elif field == "english_level":
        await state.update_data(current_field="english_level")
        await state.set_state(CandidateFSM.selecting_options)
        await callback.message.answer(
            Messages.Profile.ENTER_ENGLISH,
            reply_markup=inline.get_english_level_keyboard(),
        )
    await callback.answer()


@router.callback_query(
    inline.EditFieldCallback.filter(F.field_name == "back"), CandidateFSM.choosing_field
)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _show_profile(callback, state)
    await callback.answer()


@router.message(CandidateFSM.entering_basic_info)
async def handle_basic_input(message: Message, state: FSMContext) -> None:
    data: CandidateData = await state.get_data()
    mode: str = data.get("mode", "register")
    field_name = data.get("field_to_edit") if mode == "edit" else data.get("current_field")
    input_text: str = message.text.strip() if message.text else ""

    if not field_name:
        await message.answer(Messages.Common.INVALID_INPUT)
        return

    validator = {
        "display_name": (validators.validate_name, Messages.Profile.NAME_INVALID),
        "headline_role": (
            validators.validate_headline_role,
            Messages.Profile.ROLE_INVALID,
        ),
        "location": (validators.validate_location, Messages.Profile.LOCATION_INVALID),
    }
    if field_name in validator:
        validator_func, error_msg = validator[field_name]
        if not validator_func(input_text):
            await message.answer(error_msg)
            return

    try:
        if mode == "edit":
            payload = {}
            if field_name == "salary":
                if input_text == "/skip":
                    payload = {
                        "salary_min": None,
                        "salary_max": None,
                        "currency": "RUB",
                    }
                else:
                    parsed = validators.parse_salary(input_text)
                    if not parsed:
                        await message.answer(Messages.Profile.SALARY_PARSE_ERROR)
                        return
                    payload = {
                        "salary_min": parsed.get("salary_min"),
                        "salary_max": parsed.get("salary_max"),
                        "currency": parsed.get("currency", "RUB"),
                    }
            elif field_name == "about_me":
                payload = {"about_me": None if input_text == "/skip" else input_text}
            else:
                payload = {field_name: input_text}

            updated_profile = await api_client.candidate_api_client.update_candidate_profile(
                message.from_user.id, payload
            )
            await message.answer(
                Messages.Profile.FIELD_UPDATED
                if updated_profile
                else Messages.Profile.FIELD_UPDATE_ERROR
            )
            await state.clear()
            if updated_profile:
                await state.update_data(profile_cache=updated_profile)
            await _show_profile(message, state)

        elif mode == "register":
            await state.update_data({field_name: input_text})
            if field_name == "about_me":
                await state.update_data(about_me=None if input_text == "/skip" else input_text)
                await _ask_for_location(message, state)
            elif field_name == "display_name":
                await message.answer(Messages.Profile.ENTER_ROLE)
                await state.update_data(current_field="headline_role")
            elif field_name == "headline_role":
                await _ask_for_experience(message, state)
            elif field_name == "location":
                await state.update_data(location=input_text)
                await message.answer(Messages.Profile.ENTER_SALARY)
                await state.update_data(current_field="salary")
            elif field_name == "salary":
                salary_data = (
                    {"salary_min": None, "salary_max": None, "currency": "RUB"}
                    if input_text == "/skip"
                    else validators.parse_salary(input_text)
                )
                if not salary_data:
                    await message.answer(Messages.Profile.SALARY_PARSE_ERROR)
                    return
                await state.update_data(**salary_data)
                await state.update_data(work_modes=[])
                await message.answer(
                    Messages.Profile.WORK_MODE_SELECT,
                    reply_markup=inline.get_work_modes_keyboard(selected=set()),
                )
                await state.set_state(CandidateFSM.selecting_options)

    except Exception:
        await message.answer(Messages.Common.INVALID_INPUT)


@router.message(CandidateFSM.block_entry)
async def handle_block_entry(message: Message, state: FSMContext) -> None:
    data: CandidateData = await state.get_data()
    block_type = data.get("block_type")
    current_step = data.get("current_step")
    mode = data.get("mode", "register")
    try:
        if block_type == "experience":
            if current_step == "company":
                await state.update_data(current_exp_company=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_POSITION)
                await state.update_data(current_step="position")
            elif current_step == "position":
                await state.update_data(current_exp_position=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_START)
                await state.update_data(current_step="start_date")
            elif current_step == "start_date":
                await state.update_data(current_exp_start_date=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_END)
                await state.update_data(current_step="end_date")
            elif current_step == "end_date":
                await state.update_data(current_exp_end_date=message.text)
                await message.answer(Messages.Profile.ENTER_EXPERIENCE_RESP)
                await state.update_data(current_step="responsibilities")
            elif current_step == "responsibilities":
                key = "experiences" if mode == "register" else "new_experiences"
                updated_experiences = processors.process_new_experience(
                    data.get(key, []),
                    data.get("current_exp_company"),
                    data.get("current_exp_position"),
                    data.get("current_exp_start_date"),
                    data.get("current_exp_end_date"),
                    (
                        message.text
                        if message.text and not message.text.startswith("/skip")
                        else None
                    ),
                )
                await state.update_data({key: updated_experiences})
                await state.update_data(
                    current_exp_company=None,
                    current_exp_position=None,
                    current_exp_start_date=None,
                    current_exp_end_date=None,
                )
                await message.answer(
                    Messages.Profile.EXPERIENCE_ADDED.format(
                        name=data.get("current_exp_company", "в компании")
                    ),
                    reply_markup=inline.get_confirmation_keyboard("exp"),
                )
                await state.update_data(action_type="add_another_exp")
                await state.set_state(CandidateFSM.confirm_action)
        elif block_type == "education":
            if current_step == "level":
                await state.update_data(current_edu_level=message.text)
                await message.answer(Messages.Profile.ENTER_EDU_INSTITUTION)
                await state.update_data(current_step="institution")
            elif current_step == "institution":
                await state.update_data(current_edu_inst=message.text)
                await message.answer(Messages.Profile.ENTER_EDU_YEAR)
                await state.update_data(current_step="year")
            elif current_step == "year":
                key = "education" if mode == "register" else "new_education"
                updated = processors.process_new_education(
                    data.get(key, []),
                    data.get("current_edu_level"),
                    data.get("current_edu_inst"),
                    message.text,
                )
                await state.update_data({key: updated})
                await message.answer(
                    Messages.Profile.EDU_ADDED,
                    reply_markup=inline.get_confirmation_keyboard("edu"),
                )
                await state.update_data(action_type="add_another_edu")
                await state.set_state(CandidateFSM.confirm_action)
        elif block_type == "skill":
            if current_step == "name":
                await state.update_data(current_skill_name=message.text)
                await message.answer(
                    Messages.Profile.ENTER_SKILL_KIND,
                    reply_markup=inline.get_skill_kind_keyboard(),
                )
                await state.set_state(CandidateFSM.selecting_options)
        elif block_type == "project":
            if current_step == "title":
                await state.update_data(current_project_title=message.text)
                await message.answer(Messages.Profile.ENTER_PROJECT_DESCRIPTION)
                await state.update_data(current_step="description")
            elif current_step == "description":
                await state.update_data(
                    current_project_description=(
                        message.text
                        if message.text and not message.text.startswith("/skip")
                        else None
                    )
                )
                await message.answer(Messages.Profile.ENTER_PROJECT_LINKS)
                await state.update_data(current_step="links")
            elif current_step == "links":
                key = "projects" if mode == "register" else "new_projects"
                updated_projects = processors.process_new_project(
                    data.get(key, []),
                    data.get("current_project_title"),
                    data.get("current_project_description"),
                    (
                        message.text
                        if message.text and not message.text.startswith("/skip")
                        else None
                    ),
                )
                await state.update_data({key: updated_projects})
                await state.update_data(
                    current_project_title=None, current_project_description=None
                )
                await message.answer(
                    Messages.Profile.PROJECT_ADDED.format(
                        title=data.get("current_project_title", "проект")
                    ),
                    reply_markup=inline.get_confirmation_keyboard("project"),
                )
                await state.update_data(action_type="add_another_project")
                await state.set_state(CandidateFSM.confirm_action)
    except Exception:
        await message.answer(Messages.Common.INVALID_INPUT)


@router.callback_query(
    inline.WorkModeCallback.filter(F.mode != "done"), CandidateFSM.selecting_options
)
async def handle_work_mode_selection(
    callback: CallbackQuery, callback_data: inline.WorkModeCallback, state: FSMContext
) -> None:
    selected_modes = set((await state.get_data()).get("work_modes", []))
    mode = callback_data.mode
    if mode in selected_modes:
        selected_modes.remove(mode)
    else:
        selected_modes.add(mode)
    await state.update_data(work_modes=list(selected_modes))
    readable_modes = [formatters.WORK_MODES_MAP.get(m, m) for m in selected_modes]
    try:
        await callback.message.edit_text(
            Messages.Profile.WORK_MODE_SELECT
            + (
                "\n\n👉 <b>Текущий выбор:</b> "
                f"{', '.join(readable_modes) if readable_modes else 'пока ничего'}"
            ),
            reply_markup=inline.get_work_modes_keyboard(selected=selected_modes),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(
    inline.WorkModeCallback.filter(F.mode == "done"), CandidateFSM.selecting_options
)
async def handle_work_mode_done(callback: CallbackQuery, state: FSMContext) -> None:
    data: CandidateData = await state.get_data()
    selected_modes = data.get("work_modes", [])
    if not selected_modes:
        await callback.answer(Messages.Profile.WORK_MODES_EMPTY, show_alert=True)
        return
    readable_modes = [formatters.WORK_MODES_MAP.get(m, m) for m in selected_modes]
    await callback.message.edit_text(
        Messages.Profile.WORK_MODES_SELECTED.format(modes=", ".join(readable_modes)),
        reply_markup=None,
    )
    try:
        if data.get("mode") == "edit":
            success = await api_client.candidate_api_client.update_candidate_profile(
                callback.from_user.id, {"work_modes": selected_modes}
            )
            await callback.message.answer(
                Messages.Profile.WORK_MODE_UPDATED
                if success
                else Messages.Profile.WORK_MODE_UPDATE_ERROR
            )
            await state.clear()
            await _show_profile(callback, state)
        else:
            await _ask_for_contacts(callback.message, state)
    except Exception:
        await callback.message.answer(Messages.Common.API_ERROR)
        await state.clear()
    finally:
        await callback.answer()


@router.callback_query(inline.SkillKindCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_kind(
    callback: CallbackQuery, callback_data: inline.SkillKindCallback, state: FSMContext
) -> None:
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text(
        Messages.Profile.ENTER_SKILL_LEVEL,
        reply_markup=inline.get_skill_level_keyboard(),
    )
    await callback.answer()


@router.callback_query(inline.SkillLevelCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_level(
    callback: CallbackQuery, callback_data: inline.SkillLevelCallback, state: FSMContext
) -> None:
    data: CandidateData = await state.get_data()
    key = "skills" if data.get("mode") == "register" else "new_skills"
    try:
        updated_skills = processors.process_new_skill(
            data.get(key, []),
            data.get("current_skill_name"),
            data.get("current_skill_kind"),
            callback_data.level,
        )
        await state.update_data({key: updated_skills})
        await state.update_data(current_skill_name=None, current_skill_kind=None)
        await callback.message.edit_text(
            Messages.Profile.SKILL_ADDED.format(name=data.get("current_skill_name")),
            reply_markup=inline.get_confirmation_keyboard("skill"),
        )
        await state.update_data(action_type="add_another_skill")
        await state.set_state(CandidateFSM.confirm_action)
    except Exception:
        await callback.message.answer(Messages.Common.INVALID_INPUT)
    finally:
        await callback.answer()


@router.message(CandidateFSM.editing_contacts)
@router.message(Command("skip"), CandidateFSM.editing_contacts)
async def handle_contacts_input(message: Message, state: FSMContext) -> None:
    data: CandidateData = await state.get_data()
    mode = data.get("mode", "register")
    try:
        new_contacts = (
            processors.process_new_contacts(
                message.text if message.text and not message.text.startswith("/skip") else None
            )[0]
            or {}
        )
        if message.from_user.username:
            new_contacts["telegram"] = f"@{message.from_user.username}"
        await state.update_data(contacts=new_contacts)
        if mode == "edit":
            updated_profile = await api_client.candidate_api_client.update_candidate_profile(
                message.from_user.id, {"contacts": new_contacts}
            )
            await message.answer(
                Messages.Profile.CONTACTS_UPDATED
                if updated_profile
                else Messages.Profile.CONTACTS_UPDATE_ERROR
            )
            await state.clear()
            await _show_profile(message, state)
        else:
            await message.answer(
                Messages.Profile.CONTACTS_VISIBILITY_SELECT,
                reply_markup=inline.get_contacts_visibility_keyboard(),
            )
            await state.set_state(CandidateFSM.selecting_options)
    except Exception:
        await message.answer(Messages.Common.INVALID_INPUT)


@router.message(Command("skip"), CandidateFSM.uploading_file)
async def handle_skip_uploading(message: Message, state: FSMContext) -> None:
    data: CandidateData = await state.get_data()
    file_type = data.get("file_type")
    await message.answer(
        Messages.Profile.SKIP_UPLOAD.format(
            file_type="резюме" if file_type == "resume" else "аватара"
        )
    )
    if data.get("mode") == "edit":
        await state.clear()
        await _show_profile(message, state)
    else:
        if file_type == "resume":
            await _ask_for_avatar(message, state)
        elif file_type == "avatar":
            await _finish_registration_or_edit(message, state)


@router.message(Command("cancel"), StateFilter(CandidateFSM))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    mode = (await state.get_data()).get("mode")
    await state.clear()
    await message.answer(Messages.Common.CANCELLED)
    if mode == "edit":
        await _show_profile(message, state)


@router.message(CandidateFSM.uploading_file)
async def handle_any_file_upload(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/"):
        return
    data: CandidateData = await state.get_data()
    expected_type = data.get("file_type")
    if not expected_type:
        await message.answer(Messages.Common.STATE_ERROR)
        await state.clear()
        return
    success = False
    if expected_type == "avatar":
        if message.photo:
            success = await _process_avatar_upload(message, message.from_user.id)
        else:
            await message.answer(Messages.Profile.AVATAR_MISSING_ERROR)
            return
    elif expected_type == "resume":
        if message.document:
            success = await _process_resume_upload(message, message.from_user.id)
        else:
            await message.answer(Messages.Profile.RESUME_MISSING_ERROR)
            return

    if success:
        if data.get("mode") == "edit":
            await state.clear()
            await _show_profile(message, state)
        else:
            if expected_type == "resume":
                await _ask_for_avatar(message, state)
            elif expected_type == "avatar":
                await _finish_registration_or_edit(message, state)


@router.callback_query(
    inline.ProfileAction.filter(F.action == "delete_avatar"),
    CandidateFSM.showing_profile,
)
async def handle_delete_avatar(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    logger.info(f"User {user_id} deleting avatar")

    try:
        success = await api_client.candidate_api_client.delete_avatar(user_id)
        if success:
            await callback.answer(Messages.Profile.DELETE_AVATAR_OK)
            await state.update_data(profile_cache=None)
            await _show_profile(callback, state)
        else:
            await callback.answer(Messages.Profile.DELETE_AVATAR_ERROR, show_alert=True)

    except Exception as e:
        logger.error(f"Error deleting avatar: {e}")
        await callback.answer(Messages.Common.API_ERROR, show_alert=True)


@router.message(StateFilter(CandidateFSM))
async def invalid_input_fallback(message: Message, state: FSMContext) -> None:
    current_state: str | None = await state.get_state()
    data: dict[str, Any] = await state.get_data()
    current_field: str | None = data.get("current_field")
    block_type: str | None = data.get("block_type")
    current_step: str | None = data.get("current_step")
    logger.warning(f"Invalid input from user {message.from_user.id} in state {current_state}: \
        {message.text}")

    await message.answer(Messages.Common.INVALID_INPUT)
    if current_state == CandidateFSM.entering_basic_info:
        prompts = {
            "display_name": Messages.Profile.ENTER_NAME,
            "headline_role": Messages.Profile.ENTER_ROLE,
            "location": Messages.Profile.ENTER_LOCATION,
        }
        if current_field in prompts:
            await message.answer(prompts[current_field])
    elif current_state == CandidateFSM.block_entry:
        exp_prompts = {
            "company": Messages.Profile.ENTER_EXPERIENCE_COMPANY,
            "position": Messages.Profile.ENTER_EXPERIENCE_POSITION,
            "start_date": Messages.Profile.ENTER_EXPERIENCE_START,
            "end_date": Messages.Profile.ENTER_EXPERIENCE_END,
            "responsibilities": Messages.Profile.ENTER_EXPERIENCE_RESP,
        }
        skill_prompts = {"name": Messages.Profile.ENTER_SKILL_NAME}
        proj_prompts = {
            "title": Messages.Profile.ENTER_PROJECT_TITLE,
            "description": Messages.Profile.ENTER_PROJECT_DESCRIPTION,
            "links": Messages.Profile.ENTER_PROJECT_LINKS,
        }
        if block_type == "experience" and current_step in exp_prompts:
            await message.answer(exp_prompts[current_step])
        elif block_type == "skill" and current_step in skill_prompts:
            await message.answer(skill_prompts[current_step])
        elif block_type == "project" and current_step in proj_prompts:
            await message.answer(proj_prompts[current_step])
    elif current_state == CandidateFSM.editing_contacts:
        await message.answer(Messages.Profile.ENTER_CONTACTS)
    elif current_state == CandidateFSM.uploading_file:
        file_type = data.get("file_type")
        if file_type == "resume":
            await message.answer(Messages.Profile.UPLOAD_RESUME)
        elif file_type == "avatar":
            await message.answer(Messages.Profile.UPLOAD_AVATAR)


@router.callback_query(
    inline.ConfirmationCallback.filter(F.action == "yes"), CandidateFSM.confirm_action
)
async def handle_confirm_add_another(
    callback: CallbackQuery,
    callback_data: inline.ConfirmationCallback,
    state: FSMContext,
):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    step_prompts = {
        "exp": (Messages.Profile.ENTER_EXPERIENCE_COMPANY, "experience", "company"),
        "edu": (Messages.Profile.ENTER_EDU_LEVEL, "education", "level"),
        "skill": (Messages.Profile.ENTER_SKILL_NAME, "skill", "name"),
        "project": (Messages.Profile.ENTER_PROJECT_TITLE, "project", "title"),
    }
    if callback_data.step in step_prompts:
        prompt, block_type, current_step = step_prompts[callback_data.step]
        await callback.message.answer(prompt)
        await state.update_data(block_type=block_type, current_step=current_step)
        await state.set_state(CandidateFSM.block_entry)
    await callback.answer()


@router.callback_query(
    inline.ConfirmationCallback.filter(F.action == "no"), CandidateFSM.confirm_action
)
async def handle_confirm_finish_adding(
    callback: CallbackQuery,
    callback_data: inline.ConfirmationCallback,
    state: FSMContext,
):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    data: CandidateData = await state.get_data()
    if data.get("mode") == "edit":
        key_map = {
            "exp": "experiences",
            "edu": "education",
            "skill": "skills",
            "project": "projects",
        }
        payload_key = key_map.get(callback_data.step)
        updated_list = data.get(f"new_{payload_key}", [])
        updated = await api_client.candidate_api_client.update_candidate_profile(
            callback.from_user.id, {payload_key: updated_list}
        )
        await callback.message.answer(
            Messages.Profile.FIELD_UPDATED if updated else Messages.Profile.FIELD_UPDATE_ERROR
        )
        await state.clear()
        if updated:
            await state.update_data(profile_cache=updated)
        await _show_profile(callback.message, state)
    else:
        next_steps = {
            "start_adding_experience": _ask_for_education,
            "add_another_exp": _ask_for_education,
            "start_adding_edu": _ask_for_skills,
            "add_another_edu": _ask_for_skills,
            "add_another_skill": _ask_for_projects,
            "start_adding_project": _ask_for_english,
            "add_another_project": _ask_for_english,
        }
        handler = next_steps.get(data.get("action_type"))
        if handler:
            await handler(callback.message, state)
        else:
            await callback.message.answer(Messages.Common.STATE_ERROR)
    await callback.answer()


@router.callback_query(inline.NotificationAction.filter())
async def handle_notification_response(
    callback: CallbackQuery, callback_data: inline.NotificationAction
):
    is_granted = callback_data.action == "allow"
    req_details = await api_client.employer_api_client.get_contact_request_details(
        callback_data.req_id
    )
    success = await api_client.employer_api_client.respond_to_contact_request(
        callback_data.req_id, is_granted
    )
    if success:
        if is_granted:
            await callback.message.edit_text(Messages.Notifications.CANDIDATE_GRANTED_SUCCESS)
            if req_details:
                my_profile = await api_client.candidate_api_client.get_candidate_by_telegram_id(
                    callback.from_user.id
                )
                contact_lines = [
                    f"• {formatters.CONTACT_KEY_MAP.get(k.lower(), k.capitalize())}: "
                    f"{formatters.format_phone(v) if k == 'phone' else v}"
                    for k, v in (my_profile.get("contacts", {}) if my_profile else {}).items()
                    if v
                ]
                contact_block = (
                    "\n".join(contact_lines) if contact_lines else "Контакты не заполнены."
                )
                msg = Messages.Notifications.EMPLOYER_CONTACTS_GRANTED.format(
                    name=req_details.get("candidate_name", "Кандидат"),
                    contacts=contact_block,
                )
                try:
                    await callback.bot.send_message(
                        chat_id=req_details.get("employer_telegram_id"), text=msg
                    )
                except Exception:
                    pass
        else:
            await callback.message.edit_text(Messages.Notifications.CANDIDATE_DENIED_SUCCESS)
    else:
        await callback.answer(Messages.Profile.FIELD_UPDATE_ERROR, show_alert=True)
    await callback.answer()


@router.callback_query(inline.EnglishLevelCallback.filter(), CandidateFSM.selecting_options)
async def handle_english_level(
    callback: CallbackQuery,
    callback_data: inline.EnglishLevelCallback,
    state: FSMContext,
) -> None:
    level = None if callback_data.level == "skip" else callback_data.level
    await state.update_data(english_level=level)
    try:
        await callback.message.edit_text(
            Messages.Profile.ENGLISH_LEVEL_SELECTED.format(
                level=f"<b>{level}</b>" if level else "<b>Не указан</b>"
            )
        )
    except Exception:
        pass
    if (await state.get_data()).get("mode") == "edit":
        try:
            updated = await api_client.candidate_api_client.update_candidate_profile(
                callback.from_user.id, {"english_level": level}
            )
            if updated:
                await state.update_data(profile_cache=updated)
                await callback.answer(Messages.Profile.FIELD_UPDATED)
            else:
                await callback.answer(Messages.Profile.FIELD_UPDATE_ERROR, show_alert=True)
        except Exception:
            await callback.answer(Messages.Common.API_ERROR, show_alert=True)
        await state.clear()
        await _show_profile(callback, state)
    else:
        await _ask_for_about_me(callback, state)
