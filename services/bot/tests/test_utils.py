import pytest
from app.utils import validators, processors, formatters

def test_parse_salary():
    assert validators.parse_salary("100000") == {"salary_min": 100000, "currency": "RUB"}
    assert validators.parse_salary("100000-200000") == {"salary_min": 100000, "salary_max": 200000, "currency": "RUB"}
    assert validators.parse_salary("2000$") == {"salary_min": 2000, "currency": "USD"}
    assert validators.parse_salary("invalid") == {}

def test_validate_name():
    assert validators.validate_name("Ivan Ivanov") is True
    assert validators.validate_name("Ivan") is False

def test_parse_experience_text():
    text = "company: Google\nposition: Dev\nstart_date: 2020-01-01\nend_date: 2021-01-01\nresponsibilities: Code"
    exp = validators.parse_experience_text(text)
    assert exp.company == "Google"
    
    with pytest.raises(ValueError):
        validators.parse_experience_text("invalid")

# --- Processors ---
def test_process_new_skill():
    skills = []
    updated = processors.process_new_skill(skills, "Python", "hard", 5)
    assert len(updated) == 1
    assert updated[0]["skill"] == "Python"

def test_process_new_contacts():
    res, vis = processors.process_new_contacts("email: a@a.com")
    assert res["email"] == "a@a.com"
    assert vis == "on_request"

# --- Formatters ---
def test_format_phone():
    assert formatters.format_phone("79991234567") == "+7 (999) 123-45-67"
    assert formatters.format_phone("123") == "123"

def test_format_candidate_profile():
    profile = {
        "display_name": "Test",
        "headline_role": "Dev",
        "salary_min": 100,
        "skills": [{"skill": "Python", "kind": "hard", "level": 5}]
    }
    text = formatters.format_candidate_profile(profile)
    assert "Test" in text
    assert "Python" in text
    assert "100" in text
