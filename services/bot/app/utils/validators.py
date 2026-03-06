import logging
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

import phonenumbers
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    ValidationError,
    field_serializer,
    validator,
)

from app.core.messages import Messages

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PRESENT_ALIASES = {
    "сейчас",
    "н.в.",
    "present",
    "текущее",
    "настоящее",
    "настоящее время",
}
DATE_FORMAT = "%Y-%m-%d"


class Experience(BaseModel):
    """Модель для опыта работы."""

    company: str = Field(min_length=2, max_length=100)
    position: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: date | None
    responsibilities: str | None = Field(max_length=1000)

    class Config:
        json_encoders = {date: lambda v: v.isoformat()}

    @validator("start_date", "end_date", pre=True)
    def parse_date(cls, value):
        if isinstance(value, str):
            value = value.strip().lower()
            if value in PRESENT_ALIASES:
                return None
            try:
                parsed_date = datetime.strptime(value, DATE_FORMAT).date()
                return parsed_date
            except ValueError:
                raise ValueError(Messages.Common.INVALID_INPUT)
        return value

    @validator("start_date")
    def start_not_future(cls, v):
        if v > date.today():
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v

    @validator("end_date")
    def end_after_start(cls, v, values):
        start = values.get("start_date")
        if v and start and v < start:
            raise ValueError(Messages.Common.INVALID_INPUT)
        if v and v > date.today():
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v


class Skill(BaseModel):
    """Модель для навыка."""

    skill: str = Field(min_length=2, max_length=50)
    kind: str = Field(pattern=r"^(hard|tool|language)$")
    level: int = Field(ge=1, le=5)


class Project(BaseModel):
    """Модель для проекта."""

    title: str = Field(min_length=2, max_length=100)
    description: str | None = Field(max_length=500)
    links: HttpUrl | None = None

    @field_serializer("links")
    def serialize_links(self, v):
        return str(v) if v is not None else None


class Contacts(BaseModel):
    """Модель для контактов."""

    email: str | None = None
    phone: str | None = None
    telegram: str | None = None

    @validator("email", pre=True)
    def check_email(cls, v):
        if v and not EMAIL_RE.match(v):
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v

    @validator("phone", pre=True)
    def check_phone(cls, v):
        if v:
            try:
                parsed = phonenumbers.parse(v, None)
                if not phonenumbers.is_valid_number(parsed):
                    raise ValueError(Messages.Common.INVALID_INPUT)
            except phonenumbers.NumberParseException:
                raise ValueError(Messages.Common.INVALID_INPUT)
        return v

    @validator("telegram", pre=True)
    def check_telegram(cls, v):
        if v and not v.startswith("@"):
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v


class Education(BaseModel):
    """Модель для образования."""

    level: str = Field(min_length=2, max_length=100)
    institution: str = Field(min_length=2, max_length=200)
    year: int = Field(ge=1950, le=2100)


def parse_education_text(level: str, institution: str, year_str: str) -> Education:
    """Парсинг данных об образовании."""
    try:
        year = int(year_str.strip())
        return Education(level=level.strip(), institution=institution.strip(), year=year)
    except ValueError:
        raise ValueError("Год должен быть числом (например, 2022).")
    except ValidationError as e:
        raise ValueError(f"Ошибка валидации: {e}")


def is_valid_url(url: str) -> bool:
    """Проверка валидности URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def parse_experience_text(text: str) -> Experience:
    """Парсинг текста опыта работы."""
    lines = text.split("\n")
    data = {}
    for line in lines:
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip().lower()] = val.strip()
    required_keys = ["company", "position", "start_date"]
    if not all(k in data for k in required_keys):
        raise ValueError(f"Обязательные поля: {', '.join(required_keys)}.")
    try:
        return Experience(**data)
    except ValidationError as e:
        logger.error(f"Validation error in experience: {e}")
        raise ValueError(str(e))


def parse_skill_text(text: str) -> Skill:
    """Парсинг текста навыка."""
    parts = [part.strip() for part in text.split(",")]
    data = {}
    for part in parts:
        if ":" in part:
            key, val = part.split(":", 1)
            data[key.strip().lower()] = val.strip()
    required_keys = ["name", "kind", "level"]
    if not all(k in data for k in required_keys):
        raise ValueError(f"Обязательные поля: {', '.join(required_keys)}.")
    data["skill"] = data.pop("name")
    data["level"] = int(data["level"])
    try:
        return Skill(**data)
    except ValidationError as e:
        logger.error(f"Validation error in skill: {e}")
        raise ValueError(str(e))


def parse_project_text(title: str, description: str | None, links_text: str | None) -> Project:
    """Парсинг текста проекта."""
    data = {"title": title, "description": description, "links": links_text}
    try:
        return Project(**data)
    except ValidationError as e:
        logger.error(f"Validation error in project: {e}")
        raise ValueError(str(e))


def parse_contacts_text(text: str) -> Contacts:
    """Парсинг текста контактов в модель Contacts."""
    pairs = [pair.strip() for pair in text.split(",") if pair.strip()]
    data = {}
    for pair in pairs:
        if ":" not in pair:
            raise ValueError(Messages.Common.INVALID_INPUT)
        key, value = pair.split(":", 1)
        data[key.strip().lower()] = value.strip()
    try:
        return Contacts(**data)
    except ValidationError:
        raise ValueError(Messages.Common.INVALID_INPUT)


def validate_list_length(items: list, max_length: int = 10, item_type: str = "items") -> None:
    """Валидация длины списка."""
    if len(items) > max_length:
        raise ValueError(f"Максимум {max_length} {item_type}.")


def validate_name(name: str) -> bool:
    """Валидация ФИО: минимум 2 слова, только буквы и пробелы."""
    return bool(re.match(r"^[A-Za-zА-Яа-я\s-]+$", name) and len(name.split()) >= 2)


def validate_headline_role(role: str) -> bool:
    """Валидация роли: минимум 2 символа, не пустая."""
    return len(role.strip()) >= 2


def validate_location(location: str) -> bool:
    """Валидация локации: не пустая строка."""
    return len(location.strip()) > 0


def parse_salary(text: str) -> dict[str, Any]:
    if not text or text.strip() == "/skip":
        return {}

    raw = text.lower().strip()

    currency = "RUB"

    if any(c in raw for c in ["usd", "$", "дол"]):
        currency = "USD"

    elif any(c in raw for c in ["eur", "€", "евро"]):
        currency = "EUR"

    raw = raw.replace("т.р.", "k").replace("т.р", "k").replace("тыс", "k")
    raw = re.sub(r"(\d+)\s+([kк])", r"\1\2", raw)
    raw = re.sub(r"(\d+)[kк]", r"\g<1>000", raw)

    salary_min = None
    salary_max = None

    range_match = re.search(r"(\d+)\s*-\s*(\d+)", raw)

    if range_match:

        salary_min = int(range_match.group(1))
        salary_max = int(range_match.group(2))

        return {
            "salary_min": salary_min,
            "salary_max": salary_max,
            "currency": currency,
        }

    min_match = re.search(r"(?:от|from|>)\s*(\d+)", raw)
    max_match = re.search(r"(?:до|to|<)\s*(\d+)", raw)

    if min_match:
        salary_min = int(min_match.group(1))

    if max_match:
        salary_max = int(max_match.group(1))

    if salary_min is None and salary_max is None:

        numbers = list(map(int, re.findall(r"\d+", raw)))

        if len(numbers) == 1:

            salary_min = numbers[0]

        elif len(numbers) >= 2:

            salary_min = min(numbers)
            salary_max = max(numbers)

    result = {"currency": currency}

    if salary_min is not None:
        result["salary_min"] = salary_min

    if salary_max is not None:
        result["salary_max"] = salary_max

    return result if len(result) > 1 else {}
