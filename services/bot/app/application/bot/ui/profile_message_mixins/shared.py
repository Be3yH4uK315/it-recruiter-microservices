from __future__ import annotations

import re

from app.application.bot.constants import (
    CANDIDATE_CONTACT_LABELS,
    CANDIDATE_SKILL_KIND_LABELS,
    CANDIDATE_STATUS_LABELS,
    CANDIDATE_WORK_MODE_LABELS,
    CONTACT_VISIBILITY_HIDDEN,
    CONTACT_VISIBILITY_ON_REQUEST,
    CONTACT_VISIBILITY_PUBLIC,
    CONTACTS_VISIBILITY_LABELS,
    CURRENCY_SYMBOLS,
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    SEARCH_STATUS_LABELS,
)
from app.application.common.contracts import CandidateProfileSummary


class ProfileSharedMessagesMixin:
    @staticmethod
    def _build_candidate_profile_core_lines(
        candidate: CandidateProfileSummary,
        *,
        about_limit: int = 600,
    ) -> list[str]:
        display_name = ProfileSharedMessagesMixin._escape_markdown_text(
            candidate.display_name or "Имя не указано"
        )
        lines = [
            f"👤 *{display_name}*",
            "",
            "💼 *Должность:* "
            + (
                ProfileSharedMessagesMixin._escape_markdown_text(
                    ProfileSharedMessagesMixin._as_clean_text(candidate.headline_role)
                    or "Не указана"
                )
            ),
            "",
            "📊 *Статус:* "
            + ProfileSharedMessagesMixin._escape_markdown_text(
                ProfileSharedMessagesMixin._humanize_candidate_status(candidate.status)
            ),
            "",
            (
                "💰 *Ожидания:* "
                f"{ProfileSharedMessagesMixin._format_candidate_salary_expectations(candidate)}"
            ),
            "",
            "📍 *Локация:* "
            + (
                ProfileSharedMessagesMixin._escape_markdown_text(
                    ProfileSharedMessagesMixin._as_clean_text(candidate.location) or "Не указана"
                )
            ),
        ]
        if candidate.english_level:
            english_level_text = ProfileSharedMessagesMixin._escape_markdown_text(
                candidate.english_level
            )
            lines.extend(
                [
                    "",
                    f"🇬🇧 *Английский:* {english_level_text}",
                ]
            )
        if candidate.about_me:
            lines.extend(
                [
                    "",
                    "📝 *Обо мне:*",
                    ProfileSharedMessagesMixin._escape_markdown_text(
                        candidate.about_me[:about_limit]
                    ),
                ]
            )

        lines.extend(["", "💻 *Формат работы:*"])
        if candidate.work_modes:
            for mode in candidate.work_modes:
                lines.append(f"  • {ProfileSharedMessagesMixin._humanize_work_mode(mode)}")
        else:
            lines.append("  • Не указан")

        lines.extend(["", f"📈 *Общий опыт:* ~{candidate.experience_years:.1f} лет"])

        if candidate.experiences:
            lines.extend(["", "📜 *Опыт работы:*"])
            for experience in candidate.experiences[:3]:
                if not isinstance(experience, dict):
                    continue
                position = (
                    ProfileSharedMessagesMixin._as_clean_text(experience.get("position"))
                    or "Не указана должность"
                )
                company = (
                    ProfileSharedMessagesMixin._as_clean_text(experience.get("company"))
                    or "Не указана компания"
                )
                lines.append(
                    "  • "
                    + ProfileSharedMessagesMixin._escape_markdown_text(position)
                    + " в "
                    + ProfileSharedMessagesMixin._escape_markdown_text(company)
                )
                lines.append(
                    "    "
                    + ProfileSharedMessagesMixin._format_experience_period(
                        start_date=experience.get("start_date"),
                        end_date=experience.get("end_date"),
                    )
                )
                responsibilities = ProfileSharedMessagesMixin._as_clean_text(
                    experience.get("responsibilities")
                )
                if responsibilities:
                    lines.append(
                        "    "
                        + ProfileSharedMessagesMixin._escape_markdown_text(responsibilities[:140])
                    )

        if candidate.education:
            lines.extend(["", "🎓 *Образование:*"])
            for item in candidate.education[:5]:
                if not isinstance(item, dict):
                    continue
                level = (
                    ProfileSharedMessagesMixin._as_clean_text(item.get("level"))
                    or "Не указан уровень"
                )
                institution = (
                    ProfileSharedMessagesMixin._as_clean_text(item.get("institution"))
                    or "Не указано учреждение"
                )
                year = ProfileSharedMessagesMixin._as_clean_text(item.get("year")) or "—"
                lines.append(
                    "  • "
                    + ProfileSharedMessagesMixin._escape_markdown_text(level)
                    + " — "
                    + ProfileSharedMessagesMixin._escape_markdown_text(institution)
                    + " ("
                    + ProfileSharedMessagesMixin._escape_markdown_text(year)
                    + ")"
                )

        grouped_skills = ProfileSharedMessagesMixin._build_grouped_skills_preview(candidate.skills)
        if grouped_skills:
            lines.extend(["", "🛠 *Навыки:*"])
            lines.extend(grouped_skills)

        if candidate.projects:
            lines.extend(["", "🚀 *Проекты:*"])
            for item in candidate.projects[:3]:
                if not isinstance(item, dict):
                    continue
                title = (
                    ProfileSharedMessagesMixin._as_clean_text(item.get("title")) or "Без названия"
                )
                link = ProfileSharedMessagesMixin._extract_project_primary_link(item.get("links"))
                if link:
                    lines.append(
                        "  • "
                        + ProfileSharedMessagesMixin._format_project_title_link(
                            title=title,
                            link=link,
                        )
                    )
                else:
                    lines.append(f"  • {ProfileSharedMessagesMixin._escape_markdown_text(title)}")
                description = ProfileSharedMessagesMixin._as_clean_text(item.get("description"))
                if description:
                    lines.append(
                        "    " + ProfileSharedMessagesMixin._escape_markdown_text(description[:140])
                    )

        return lines

    @staticmethod
    def _build_candidate_contacts_block_lines(
        *,
        contacts: dict[str, str | None] | None,
        contacts_visibility: str | None,
        can_view_contacts: bool,
        contacts_title: str,
        include_visibility: bool = True,
        empty_contacts_text: str = "  • Не заполнены",
        unavailable_contacts_text: str = "  • Недоступны для просмотра",
    ) -> list[str]:
        lines: list[str] = []
        if include_visibility:
            lines.append(
                "👁 *Видимость контактов:* "
                + ProfileSharedMessagesMixin._humanize_contacts_visibility_for_profile(
                    contacts_visibility
                )
            )
        lines.append(contacts_title)
        if can_view_contacts:
            contact_lines = ProfileSharedMessagesMixin._build_owner_contact_lines(contacts)
            if contact_lines:
                lines.extend(contact_lines)
            else:
                lines.append(empty_contacts_text)
            return lines

        lines.append(unavailable_contacts_text)
        return lines

    @staticmethod
    def _build_pending_upload_recovery_message(
        *,
        role: str,
        recovered_kinds: list[str],
        state_reset: bool,
    ) -> str:
        lines = [
            "Обнаружили незавершенную загрузку файла после перезапуска сервиса.",
        ]

        if recovered_kinds:
            unique_kinds: list[str] = []
            for kind in recovered_kinds:
                if kind not in unique_kinds:
                    unique_kinds.append(kind)
            pretty_kinds = ", ".join(
                ProfileSharedMessagesMixin._humanize_pending_upload_target_kind(kind)
                for kind in unique_kinds
            )
            lines.append(f"Затронутые файлы: {pretty_kinds}.")

        if state_reset:
            lines.append("Технический шаг загрузки сброшен для безопасного восстановления.")

        if role == ROLE_CANDIDATE:
            lines.append(
                "Открой раздел `Загрузить аватар` или `Загрузить резюме` и отправь файл снова."
            )
        elif role == ROLE_EMPLOYER:
            lines.append(
                "Открой раздел `Загрузить аватар компании` или `Загрузить документ компании` "
                "и отправь файл снова."
            )
        else:
            lines.append("Повтори отправку файла из соответствующего раздела меню.")

        return "\n".join(lines)

    @staticmethod
    def _humanize_pending_upload_target_kind(target_kind: str) -> str:
        normalized = target_kind.strip().lower()
        mapping = {
            "candidate_avatar": "аватар кандидата",
            "candidate_resume": "резюме кандидата",
            "employer_avatar": "аватар компании",
            "employer_document": "документ компании",
        }
        return mapping.get(normalized, target_kind)

    @staticmethod
    def _build_skills_preview(skills: list[dict] | None, *, limit: int) -> str | None:
        if not skills:
            return None
        names: list[str] = []
        for item in skills:
            skill_name = ProfileSharedMessagesMixin._as_clean_text(item.get("skill"))
            if skill_name:
                names.append(skill_name)
            if len(names) >= limit:
                break
        if not names:
            return None
        if len(skills) > limit:
            return f"{', '.join(names)} +{len(skills) - limit}"
        return ", ".join(names)

    @staticmethod
    def _build_last_experience_preview(experiences: list[dict] | None) -> str | None:
        if not experiences:
            return None
        first = experiences[0]
        if not isinstance(first, dict):
            return None
        company = ProfileSharedMessagesMixin._as_clean_text(first.get("company"))
        position = ProfileSharedMessagesMixin._as_clean_text(first.get("position"))
        if company and position:
            return f"{position} @ {company}"
        return position or company

    @staticmethod
    def _humanize_contacts_visibility(value: str) -> str:
        normalized = value.strip().lower()
        if normalized == CONTACT_VISIBILITY_PUBLIC:
            return "открыты"
        if normalized == CONTACT_VISIBILITY_ON_REQUEST:
            return "по запросу"
        if normalized == CONTACT_VISIBILITY_HIDDEN:
            return "скрыты"
        return value

    @staticmethod
    def _humanize_search_status(value: str | None) -> str:
        if not value:
            return "—"
        normalized = value.strip().lower()
        return SEARCH_STATUS_LABELS.get(normalized, value)

    @staticmethod
    def _as_clean_text(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _escape_markdown_text(value: object) -> str:
        escaped = str(value).replace("\\", "\\\\")
        for char in ("_", "*", "[", "]", "`"):
            escaped = escaped.replace(char, f"\\{char}")
        return escaped

    @staticmethod
    def _humanize_candidate_status(value: str | None) -> str:
        if not value:
            return "Не указан"
        normalized = value.strip().lower()
        return CANDIDATE_STATUS_LABELS.get(normalized, value)

    @staticmethod
    def _humanize_work_mode(value: str) -> str:
        normalized = value.strip().lower()
        return CANDIDATE_WORK_MODE_LABELS.get(normalized, value)

    @staticmethod
    def _humanize_contacts_visibility_for_profile(value: str | None) -> str:
        if not value:
            return "Не указана"
        normalized = value.strip().lower()
        return CONTACTS_VISIBILITY_LABELS.get(normalized, value)

    @staticmethod
    def _format_candidate_salary_expectations(candidate: CandidateProfileSummary) -> str:
        salary_min = candidate.salary_min
        salary_max = candidate.salary_max
        if salary_min is None and salary_max is None:
            return "Не указаны"

        currency_code = (candidate.currency or "").strip().upper()
        currency_symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)

        if salary_min is not None and salary_max is not None:
            return (
                f"{ProfileSharedMessagesMixin._format_number_with_spaces(salary_min)} – "
                f"{ProfileSharedMessagesMixin._format_number_with_spaces(salary_max)} "
                f"{currency_symbol}"
            ).rstrip()
        if salary_min is not None:
            salary_min_text = ProfileSharedMessagesMixin._format_number_with_spaces(salary_min)
            return f"от {salary_min_text} {currency_symbol}".rstrip()
        return (
            "до "
            f"{ProfileSharedMessagesMixin._format_number_with_spaces(salary_max or 0)} "
            f"{currency_symbol}"
        ).rstrip()

    @staticmethod
    def _format_number_with_spaces(value: int) -> str:
        return f"{value:,}".replace(",", " ")

    @staticmethod
    def _format_experience_period(
        *,
        start_date: object,
        end_date: object,
    ) -> str:
        start = ProfileSharedMessagesMixin._format_profile_date(start_date)
        end = ProfileSharedMessagesMixin._format_profile_date(end_date) if end_date else "н.в."
        return f"{start} – {end}"

    @staticmethod
    def _format_profile_date(value: object) -> str:
        normalized = ProfileSharedMessagesMixin._as_clean_text(value)
        if not normalized:
            return "—"
        if len(normalized) >= 10:
            return normalized[:10].replace("-", ".")
        return normalized.replace("-", ".")

    @staticmethod
    def _build_grouped_skills_preview(skills: list[dict] | None) -> list[str]:
        if not skills:
            return []

        grouped: dict[str, list[str]] = {
            "hard": [],
            "tool": [],
            "language": [],
            "soft": [],
        }
        for item in skills:
            if not isinstance(item, dict):
                continue
            skill_name = ProfileSharedMessagesMixin._as_clean_text(item.get("skill"))
            if not skill_name:
                continue
            kind = str(item.get("kind", "hard")).strip().lower()
            if kind not in grouped:
                kind = "hard"
            level = item.get("level")
            if isinstance(level, int):
                grouped[kind].append(
                    f"{ProfileSharedMessagesMixin._escape_markdown_text(skill_name)} ({level}/5)"
                )
            else:
                grouped[kind].append(ProfileSharedMessagesMixin._escape_markdown_text(skill_name))

        lines: list[str] = []
        for kind in ["hard", "tool", "language", "soft"]:
            entries = grouped.get(kind) or []
            if not entries:
                continue
            label = CANDIDATE_SKILL_KIND_LABELS.get(kind, kind)
            lines.append(
                f"  • *{label}:* {ProfileSharedMessagesMixin._join_limited(entries, limit=8)}"
            )
        return lines

    @staticmethod
    def _join_limited(items: list[str], *, limit: int) -> str:
        if len(items) <= limit:
            return ", ".join(items)
        head = ", ".join(items[:limit])
        return f"{head} +{len(items) - limit}"

    @staticmethod
    def _extract_project_primary_link(links: object) -> str | None:
        if isinstance(links, str):
            return ProfileSharedMessagesMixin._as_clean_text(links)
        if isinstance(links, dict):
            for value in links.values():
                normalized = ProfileSharedMessagesMixin._as_clean_text(value)
                if normalized:
                    return normalized
            return None
        if isinstance(links, (list, tuple)):
            for item in links:
                normalized = ProfileSharedMessagesMixin._as_clean_text(item)
                if normalized:
                    return normalized
            return None
        return None

    @staticmethod
    def _format_project_title_link(*, title: str, link: str) -> str:
        normalized_link = link.strip()
        lowered = normalized_link.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            return (
                f"{ProfileSharedMessagesMixin._escape_markdown_text(title)} "
                f"({ProfileSharedMessagesMixin._escape_markdown_text(normalized_link)})"
            )
        if " " in normalized_link or ")" in normalized_link:
            return (
                f"{ProfileSharedMessagesMixin._escape_markdown_text(title)} "
                f"({ProfileSharedMessagesMixin._escape_markdown_text(normalized_link)})"
            )

        escaped_title = title.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
        return f"[{escaped_title}]({normalized_link})"

    @staticmethod
    def _build_owner_contact_lines(contacts: dict[str, str | None] | None) -> list[str]:
        if not isinstance(contacts, dict):
            return []
        lines: list[str] = []
        for key in ["email", "phone", "telegram", "website"]:
            value_raw = contacts.get(key)
            value = ProfileSharedMessagesMixin._as_clean_text(value_raw)
            if not value:
                continue
            label = CANDIDATE_CONTACT_LABELS.get(key, key)
            if key == "phone":
                value = ProfileSharedMessagesMixin._format_phone_for_profile(value)
            lines.append(
                "  • *"
                + ProfileSharedMessagesMixin._escape_markdown_text(label)
                + ":* "
                + ProfileSharedMessagesMixin._escape_markdown_text(value)
            )
        return lines

    @staticmethod
    def _format_phone_for_profile(phone: str) -> str:
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 11 and digits[0] in {"7", "8"}:
            normalized = f"7{digits[1:]}"
            return (
                f"+7 ({normalized[1:4]}) " f"{normalized[4:7]}-{normalized[7:9]}-{normalized[9:]}"
            )
        if len(digits) == 10:
            return f"+7 ({digits[:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:]}"
        return phone
