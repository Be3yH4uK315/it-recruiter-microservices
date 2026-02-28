from typing import Dict, Any, List

from app.utils import validators

def process_new_experience(
    experiences: List[Dict[str, Any]],
    company: str,
    position: str,
    start_date: str,
    end_date: str,
    responsibilities: str | None
) -> List[Dict[str, Any]]:
    """
    Принимает текущий список опыта и данные для нового, возвращает обновленный список.
    """
    if not all([company, position, start_date]):
        raise ValueError("Отсутствуют обязательные данные об опыте работы.")
        
    exp_text = (
        f"company: {company}\n"
        f"position: {position}\n"
        f"start_date: {start_date}\n"
        f"end_date: {end_date}\n"
        f"responsibilities: {responsibilities or ''}"
    )
    
    new_experience = validators.parse_experience_text(exp_text)
    updated_experiences = experiences + [new_experience.model_dump(mode='json')]
    validators.validate_list_length(updated_experiences, max_length=10, item_type="опытов работы")
    
    return updated_experiences

def process_new_skill(
    skills: List[Dict[str, Any]], 
    skill_name: str, 
    skill_kind: str, 
    skill_level: int
) -> List[Dict[str, Any]]:
    """
    Принимает текущий список навыков и данные для нового, возвращает обновленный список.
    """
    if not skill_name or not skill_kind:
        raise ValueError("Отсутствуют обязательные данные о навыке.")
            
    skill_text = f"name: {skill_name}, kind: {skill_kind}, level: {skill_level}"
    new_skill = validators.parse_skill_text(skill_text)
    
    updated_skills = skills + [new_skill.model_dump(mode='json')]
    validators.validate_list_length(updated_skills, max_length=20, item_type="навыков")
    
    return updated_skills

def process_new_project(
    projects: List[Dict[str, Any]],
    title: str,
    description: str | None,
    links_text: str | None
) -> List[Dict[str, Any]]:
    """
    Принимает текущий список проектов и данные для нового, возвращает обновленный список.
    """
    if not title:
        raise ValueError("Отсутствует заголовок проекта.")
        
    new_project = validators.parse_project_text(title=title, description=description, links_text=links_text)
    updated_projects = projects + [new_project.model_dump(mode='json')]
    validators.validate_list_length(updated_projects, max_length=10, item_type="проектов")
    
    return updated_projects

def process_new_contacts(contacts_text: str | None) -> tuple[dict | None, str]:
    """
    Принимает текст с контактами, возвращает словарь контактов и видимость.
    """
    if contacts_text:
        new_contacts = validators.parse_contacts_text(contacts_text)
        return new_contacts.model_dump(mode='json'), "on_request"
    return None, "hidden"

def process_new_education(
    education_list: List[Dict[str, Any]],
    level: str,
    institution: str,
    year: str
) -> List[Dict[str, Any]]:
    """
    Добавляет новое образование в список.
    """
    if not all([level, institution, year]):
        raise ValueError("Все поля образования обязательны.")
    
    new_edu = validators.parse_education_text(level, institution, year)
    updated_list = education_list + [new_edu.model_dump(mode='json')]
    validators.validate_list_length(updated_list, max_length=5, item_type="записей об образовании")
    
    return updated_list