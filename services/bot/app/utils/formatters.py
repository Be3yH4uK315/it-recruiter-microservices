import re
from typing import Any

WORK_MODES_MAP = {"office": "Офис", "remote": "Удаленка", "hybrid": "Гибрид"}

WORK_MODE_MAP = {"office": "🏢 Офис", "remote": "🏠 Удаленно", "hybrid": "📌 Гибрид"}

VISIBILITY_MAP = {
    "on_request": "🔒 По запросу",
    "public": "🌍 Видны всем",
    "hidden": "🚫 Скрыты от всех",
}

STATUS_MAP = {
    "active": "✅ Активен (виден в поиске)",
    "hidden": "🚫 Скрыт (не виден в поиске)",
    "blocked": "⛔ Заблокирован",
}

SKILL_KIND_MAP = {
    "hard": "🧠 Хард скиллы",
    "tool": "🛠 Инструменты",
    "language": "🗣 Языки",
}

CONTACT_KEY_MAP = {
    "email": "📧 Email",
    "phone": "📱 Телефон",
    "telegram": "✈️ Telegram",
}

CURRENCY_MAP = {"RUB": "₽", "USD": "$", "EUR": "€"}


def format_salary(min_val, max_val, curr):
    c_symbol = CURRENCY_MAP.get(curr, curr)
    if min_val and max_val:
        return f"{min_val:,} – {max_val:,} {c_symbol}".replace(",", " ")
    elif min_val:
        return f"от {min_val:,} {c_symbol}".replace(",", " ")
    elif max_val:
        return f"до {max_val:,} {c_symbol}".replace(",", " ")
    return "Не указана"


def format_phone(phone: str) -> str:
    """Простое форматирование телефона, если он пришел как 7999..."""
    clean = re.sub(r"\D", "", phone)
    if len(clean) == 11 and clean.startswith("7"):
        return f"+7 ({clean[1:4]}) {clean[4:7]}-{clean[7:9]}-{clean[9:]}"
    return phone


def format_candidate_profile(profile: dict[str, Any], is_owner: bool = False) -> str:
    """Форматирование профиля для отображения."""
    status_raw = profile.get("status", "active")
    status_text = STATUS_MAP.get(status_raw, status_raw)

    text = (
        f"<b>👤 {profile.get('display_name', 'Имя не указано')}</b>\n\n"
        f"<b>💼 Должность:</b> {profile.get('headline_role', 'Не указана')}\n\n"
    )

    if profile.get("match_score"):
        score_percent = min(100, int(profile["match_score"] * 100))
        text += f"<b>🎯 Совпадение:</b> {score_percent}%\n"
    else:
        text += f"<b>📊 Статус:</b> {status_text}\n"

    text += "\n"

    sal_min = profile.get("salary_min")
    sal_max = profile.get("salary_max")
    curr = profile.get("currency", "RUB")

    if sal_min or sal_max:
        sal_text = format_salary(sal_min, sal_max, curr)
        text += f"<b>💰 Ожидания:</b> {sal_text}\n\n"

    text += f"<b>📍 Локация:</b> {profile.get('location', 'Не указана')}\n\n"

    if profile.get("english_level"):
        text += f"<b>🇬🇧 Английский:</b> {profile['english_level']}\n"

    if profile.get("about_me"):
        about = profile["about_me"]
        if len(about) > 500:
            about = about[:500] + "..."
        text += f"<b>📝 Обо мне:</b>\n<i>{about}</i>\n\n"

    modes = profile.get("work_modes") or []
    if modes:
        text += "<b>💻 Формат работы:</b>\n"
        for m in modes:
            text += f"  • {WORK_MODE_MAP.get(m, m)}\n"
        text += "\n"
    else:
        text += "<b>💻 Формат работы:</b> Не указан\n"

    total_exp = profile.get("experience_years", 0)
    text += f"<b>📈 Общий опыт:</b> ~{total_exp} лет\n\n"

    experiences = profile.get("experiences", [])
    if experiences:
        text += "<b>📜 Опыт работы:</b>\n"
        for exp in experiences[:3]:
            end_date = (exp.get("end_date") or "н.в.").replace("-", ".")
            start_date = (exp.get("start_date") or "").replace("-", ".")
            text += f"  • <b>{exp.get('position', 'Не указана')}</b> в \
                    {exp.get('company', 'Не указана')}\n" f"    <i>{start_date} – {end_date}</i>\n"
            if exp.get("responsibilities"):
                resp = exp.get("responsibilities")
                if len(resp) > 100:
                    resp = resp[:100] + "..."
                text += f"    <i>{resp}</i>\n"
            text += "\n"

    education = profile.get("education", [])
    if education:
        text += "<b>🎓 Образование:</b>\n"
        for edu in education:
            text += f"  • {edu.get('level')} — {edu.get('institution')} \
                ({edu.get('year')})\n"
        text += "\n"

    skills = profile.get("skills", [])
    if skills:
        text += "<b>🛠 Навыки:</b>\n"

        is_string_list = isinstance(skills[0], str)

        if is_string_list:
            display_skills = skills[:15]
            text += f"  • {', '.join(display_skills)}\n"
            if len(skills) > 15:
                text += f"  • ...и еще {len(skills)-15}\n"
        else:
            groups = {"hard": [], "tool": [], "language": []}
            for s in skills:
                k = s.get("kind", "hard")
                level_str = f" ({s['level']}/5)" if s.get("level") else ""
                if k in groups:
                    groups[k].append(f"{s['skill']}{level_str}")

            for kind, label in SKILL_KIND_MAP.items():
                if groups.get(kind):
                    text += f"  • {label}: {', '.join(groups[kind])}\n"

        text += "\n"

    projects = profile.get("projects", [])
    if projects:
        text += "<b>🚀 Проекты:</b>\n"
        for p in projects[:3]:
            title = p.get("title", "Без названия")
            link = None
            if p.get("links"):
                if isinstance(p["links"], dict):
                    link = p["links"].get("main_link") or list(p["links"].values())[0]
                elif isinstance(p["links"], str):
                    link = p["links"]

            title_html = f"<a href='{link}'>{title}</a>" if link else title
            text += f"  • <b>{title_html}</b>\n"
            if p.get("description"):
                text += f"    <i>{p.get('description')[:100]}...</i>\n"
        text += "\n"

    vis_raw = profile.get("contacts_visibility", "on_request")
    vis_text = VISIBILITY_MAP.get(vis_raw, vis_raw)

    if is_owner:
        text += f"<b>👁 Видимость контактов:</b> {vis_text}\n"
        contacts = profile.get("contacts")
        if contacts:
            text += "<b>📞 Ваши контакты:</b>\n"
            for k, v in contacts.items():
                if v:
                    lbl = CONTACT_KEY_MAP.get(k.lower(), k.capitalize())
                    val = format_phone(v) if k == "phone" else v
                    text += f"  • {lbl}: {val}\n"
        else:
            text += "<b>📞 Ваши контакты:</b> Не заполнены\n"

    else:
        if vis_raw == "public":
            text += "<b>📞 Контакты:</b> 🌍 Открыты (нажмите кнопку ниже)\n"
        else:
            text += "<b>📞 Контакты:</b> 🔒 По запросу (нажмите кнопку ниже)\n"

    return text
