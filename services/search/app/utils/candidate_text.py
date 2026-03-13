from typing import Any


def build_candidate_text(candidate: dict[str, Any]) -> str:
    """
    Универсальная функция для генерации текстового представления кандидата.
    Обеспечивает консистентность данных между поиском по векторам и CrossEncoder'ом.
    """
    parts = []
    
    if position := candidate.get("position"):
        parts.append(f"Позиция: {position}")
        
    if about := candidate.get("about"):
        parts.append(f"О себе: {about}")
        
    skills = candidate.get("skills", [])
    if skills:
        skill_names = [s["skill"] if isinstance(s, dict) else s for s in skills]
        parts.append(f"Навыки: {', '.join(skill_names)}")
        
    experience = candidate.get("experience", [])
    if experience:
        exp_texts = [
            f"{exp.get('position', '')} в {exp.get('company', '')}: {exp.get('description', '')}" 
            for exp in experience
        ]
        parts.append("Опыт работы: " + " | ".join(exp_texts))
        
    return ". ".join(filter(None, parts))