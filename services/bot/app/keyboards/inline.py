from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.formatters import WORK_MODES_MAP


class ContactsVisibilityCallback(CallbackData, prefix="vis"):
    visibility: str


class SkillKindCallback(CallbackData, prefix="skill_kind"):
    kind: str


class SkillLevelCallback(CallbackData, prefix="skill_level"):
    level: int


class ConfirmationCallback(CallbackData, prefix="confirm"):
    action: Literal["yes", "no"]
    step: str


class RoleCallback(CallbackData, prefix="role"):
    role_name: str


class EditFieldCallback(CallbackData, prefix="edit_field"):
    field_name: str


class WorkModeCallback(CallbackData, prefix="work_mode"):
    mode: str


class ProfileAction(CallbackData, prefix="profile_action"):
    action: str


class SearchResultDecision(CallbackData, prefix="search_dec"):
    action: str
    candidate_id: str


class SearchResultAction(CallbackData, prefix="search_res"):
    action: str
    candidate_id: str


class NotificationAction(CallbackData, prefix="notify"):
    action: str
    req_id: str


class EnglishLevelCallback(CallbackData, prefix="eng"):
    level: str


def get_role_selection_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="👤 Я кандидат",
                callback_data=RoleCallback(role_name="candidate").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🏢 Я работодатель",
                callback_data=RoleCallback(role_name="employer").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_contacts_visibility_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="По запросу",
                callback_data=ContactsVisibilityCallback(visibility="on_request").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="Публичные",
                callback_data=ContactsVisibilityCallback(visibility="public").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="Скрытые",
                callback_data=ContactsVisibilityCallback(visibility="hidden").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_work_modes_keyboard(selected: set[str] = set()) -> InlineKeyboardMarkup:
    mode_buttons = [
        InlineKeyboardButton(
            text=f"{'✅ ' if m in selected else ''}{name}",
            callback_data=WorkModeCallback(mode=m).pack(),
        )
        for m, name in WORK_MODES_MAP.items()
    ]
    keyboard = [mode_buttons[i : i + 2] for i in range(0, len(mode_buttons), 2)]
    keyboard.append(
        [InlineKeyboardButton(text="🏁 Готово", callback_data=WorkModeCallback(mode="done").pack())]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_profile_actions_keyboard(
    has_avatar: bool = False, has_resume: bool = False, is_hidden: bool = False
) -> InlineKeyboardMarkup:
    """Главное меню профиля."""
    keyboard = []
    keyboard.append(
        [
            InlineKeyboardButton(
                text="✏️ Редактировать профиль",
                callback_data=ProfileAction(action="edit").pack(),
            )
        ]
    )

    row_avatar = []
    if has_avatar:
        row_avatar.append(
            InlineKeyboardButton(
                text="❌ Удалить аватар",
                callback_data=ProfileAction(action="delete_avatar").pack(),
            )
        )
        row_avatar.append(
            InlineKeyboardButton(
                text="🖼️ Обновить аватар",
                callback_data=ProfileAction(action="upload_avatar").pack(),
            )
        )
    else:
        row_avatar.append(
            InlineKeyboardButton(
                text="🖼️ Загрузить аватар",
                callback_data=ProfileAction(action="upload_avatar").pack(),
            )
        )
    keyboard.append(row_avatar)

    row_resume = []
    if has_resume:
        row_resume.append(
            InlineKeyboardButton(
                text="📥 Скачать резюме",
                callback_data=ProfileAction(action="download_my_resume").pack(),
            )
        )
        row_resume.append(
            InlineKeyboardButton(
                text="📄 Обновить",
                callback_data=ProfileAction(action="upload_resume").pack(),
            )
        )
        row_resume.append(
            InlineKeyboardButton(
                text="❌ Удалить",
                callback_data=ProfileAction(action="delete_resume").pack(),
            )
        )
    else:
        row_resume.append(
            InlineKeyboardButton(
                text="📄 Загрузить резюме",
                callback_data=ProfileAction(action="upload_resume").pack(),
            )
        )
    keyboard.append(row_resume)

    status_text = "✅ Сделать активным" if is_hidden else "🚫 Скрыть профиль"
    status_action = "set_active" if is_hidden else "set_hidden"
    keyboard.append(
        [
            InlineKeyboardButton(
                text=status_text,
                callback_data=ProfileAction(action=status_action).pack(),
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_initial_search_keyboard(candidate_id: str, has_resume: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="👍 Подходит",
                callback_data=SearchResultDecision(action="like", candidate_id=candidate_id).pack(),
            ),
            InlineKeyboardButton(
                text="👎 Не подходит",
                callback_data=SearchResultDecision(
                    action="dislike", candidate_id=candidate_id
                ).pack(),
            ),
        ]
    ]
    if has_resume:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="📄 Скачать резюме",
                    callback_data=SearchResultAction(
                        action="get_resume", candidate_id=candidate_id
                    ).pack(),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=SearchResultAction(action="next", candidate_id="0").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_liked_candidate_keyboard(
    candidate_id: str, visibility: str = "on_request"
) -> InlineKeyboardMarkup:
    contact_btn_text = "📞 Показать контакты" if visibility == "public" else "✉️ Запросить контакты"
    keyboard = [
        [
            InlineKeyboardButton(
                text=contact_btn_text,
                callback_data=SearchResultAction(
                    action="contact", candidate_id=candidate_id
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=SearchResultAction(action="next", candidate_id="0").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_profile_edit_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора полей для редактирования."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="ФИО",
                callback_data=EditFieldCallback(field_name="display_name").pack(),
            ),
            InlineKeyboardButton(
                text="Должность",
                callback_data=EditFieldCallback(field_name="headline_role").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Навыки",
                callback_data=EditFieldCallback(field_name="skills").pack(),
            ),
            InlineKeyboardButton(
                text="Опыт",
                callback_data=EditFieldCallback(field_name="experiences").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Образование",
                callback_data=EditFieldCallback(field_name="education").pack(),
            ),
            InlineKeyboardButton(
                text="Проекты",
                callback_data=EditFieldCallback(field_name="projects").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Английский",
                callback_data=EditFieldCallback(field_name="english_level").pack(),
            ),
            InlineKeyboardButton(
                text="Обо мне",
                callback_data=EditFieldCallback(field_name="about_me").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Зарплата",
                callback_data=EditFieldCallback(field_name="salary").pack(),
            ),
            InlineKeyboardButton(
                text="Локация",
                callback_data=EditFieldCallback(field_name="location").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Формат работы",
                callback_data=EditFieldCallback(field_name="work_modes").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="Мои контакты",
                callback_data=EditFieldCallback(field_name="contacts").pack(),
            ),
            InlineKeyboardButton(
                text="Видимость контактов",
                callback_data=EditFieldCallback(field_name="contacts_visibility").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Назад к профилю",
                callback_data=EditFieldCallback(field_name="back").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_skill_kind_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Hard Skill", callback_data=SkillKindCallback(kind="hard").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="Инструмент (Tool)",
                callback_data=SkillKindCallback(kind="tool").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="Язык (Language)",
                callback_data=SkillKindCallback(kind="language").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_skill_level_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text=str(i), callback_data=SkillLevelCallback(level=i).pack())
            for i in range(1, 6)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard(step: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Да",
                callback_data=ConfirmationCallback(action="yes", step=step).pack(),
            ),
            InlineKeyboardButton(
                text="🏁 Нет",
                callback_data=ConfirmationCallback(action="no", step=step).pack(),
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_notification_keyboard(request_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Разрешить",
                callback_data=NotificationAction(action="allow", req_id=request_id).pack(),
            ),
            InlineKeyboardButton(
                text="🚫 Отклонить",
                callback_data=NotificationAction(action="deny", req_id=request_id).pack(),
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_english_level_keyboard() -> InlineKeyboardMarkup:
    levels = [
        ("A1 (Beginner)", "A1"),
        ("A2 (Elementary)", "A2"),
        ("B1 (Intermediate)", "B1"),
        ("B2 (Upper-Int.)", "B2"),
        ("C1 (Advanced)", "C1"),
        ("C2 (Proficiency)", "C2"),
    ]

    buttons = [
        InlineKeyboardButton(text=name, callback_data=EnglishLevelCallback(level=code).pack())
        for name, code in levels
    ]
    keyboard = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append(
        [
            InlineKeyboardButton(
                text="❌ Не указывать",
                callback_data=EnglishLevelCallback(level="skip").pack(),
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
