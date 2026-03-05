from typing import List, Dict, Any, Tuple
import numpy as np
import structlog

from app.core.resources import resources
from app.core.config import settings
from app.models.search import SearchFilters

logger = structlog.get_logger()

class RankerService:
    async def rerank_candidates(
        self, 
        query_text: str, 
        candidates: List[Dict[str, Any]], 
        filters: SearchFilters
    ) -> List[Dict[str, Any]]:
        
        if not candidates: return []
        
        pairs = []
        for cand in candidates:
            pairs.append([query_text, self._construct_candidate_text(cand)])

        try:
            raw_scores = await resources.predict_ranker_async(pairs)
            ml_scores = 1 / (1 + np.exp(-raw_scores))
        except Exception as e:
            logger.error(f"Ranker inference failed: {e}")
            ml_scores = [0.5] * len(candidates)

        scored_candidates = []
        for i, cand in enumerate(candidates):
            final_score, factors = self._calculate_multiplicative_score(
                cand, filters, float(ml_scores[i])
            )
            cand["match_score"] = final_score
            cand["score_explanation"] = factors
            scored_candidates.append(cand)

        scored_candidates.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_candidates

    def _calculate_multiplicative_score(
        self, 
        candidate: Dict, 
        filters: SearchFilters, 
        ml_score: float
    ) -> Tuple[float, Dict]:
        """
        Multiplicative Scoring Model:
        Score = ML_Prob * SkillFactor * ExpFactor * LocFactor * SalFactor * EngFactor
        """
        factors = {"ml_score": round(ml_score, 4)}
        
        skill_factor = 1.0
        
        cand_skills_dict = {}
        for s in candidate.get("skills", []):
            if isinstance(s, dict) and "skill" in s and "level" in s:
                cand_skills_dict[s["skill"].lower()] = float(s["level"])

        if filters.must_skills:
            required = set(filters.must_skills)
            matched_score = 0.0
            
            for req in required:
                if req in cand_skills_dict:
                    level = cand_skills_dict[req]
                    
                    if level >= 3:
                        item_score = 1.0 + (level - 3) * 0.1
                    else:
                        item_score = 1.0 - (3 - level) * 0.2
                        
                    matched_score += item_score
            
            avg_match = matched_score / len(required)
            
            skill_factor = settings.FACTOR_NO_SKILLS + ((1.0 - settings.FACTOR_NO_SKILLS) * avg_match)

        if filters.nice_skills:
            nice_bonus = 0.0
            for nice in set(filters.nice_skills):
                if nice in cand_skills_dict:
                    level = cand_skills_dict[nice]
                    nice_bonus += (level / 5.0) * 0.1 
            
            skill_factor = min(1.5, skill_factor + nice_bonus)

        factors["skill_factor"] = round(skill_factor, 2)

        exp_factor = 1.0
        cand_exp = candidate.get("experience_years", 0)
        
        if filters.experience_min is not None and cand_exp < filters.experience_min:
            diff = filters.experience_min - cand_exp
            exp_factor = max(0.5, 1.0 - (diff * 0.15))
        elif filters.experience_max is not None and cand_exp > filters.experience_max:
            diff = cand_exp - filters.experience_max
            exp_factor = max(0.8, 1.0 - (diff * 0.05))
            
        factors["exp_factor"] = round(exp_factor, 2)
        
        loc_factor = 1.0
        if filters.location and candidate.get("location"):
            if filters.location.lower() in candidate["location"].lower():
                loc_factor = settings.FACTOR_LOCATION_MATCH
        factors["loc_factor"] = loc_factor

        sal_factor = 1.0
        if filters.salary_max and candidate.get("salary_min"):
            if candidate["salary_min"] > filters.salary_max:
                ratio = candidate["salary_min"] / filters.salary_max
                sal_factor = max(0.5, 1.0 - (ratio - 1.0))
        factors["sal_factor"] = round(sal_factor, 2)

        eng_factor = 1.0
        if filters.english_level:
            levels = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
            req_lvl = levels.get(filters.english_level.upper(), 0)
            
            cand_lvl_str = candidate.get("english_level")
            cand_lvl = levels.get(cand_lvl_str.upper() if cand_lvl_str else "", 0)
            
            if cand_lvl == 0:
                eng_factor = 0.8
            elif cand_lvl < req_lvl:
                diff = req_lvl - cand_lvl
                eng_factor = max(0.5, 1.0 - (diff * 0.15))
            elif cand_lvl > req_lvl:
                eng_factor = 1.05
        factors["eng_factor"] = round(eng_factor, 2)

        final_score = ml_score * skill_factor * exp_factor * loc_factor * sal_factor * eng_factor
        return round(final_score, 4), factors

    def _construct_candidate_text(self, cand: Dict) -> str:
        parts = []
        if r := cand.get("headline_role"): parts.append(f"Role: {r}")
        if s := cand.get("skills"):
            s_str = ", ".join(s) if isinstance(s[0], str) else ", ".join(x['skill'] for x in s)
            parts.append(f"Skills: {s_str}")
        if e := cand.get("education_text"): parts.append(f"Edu: {e}")
        if a := cand.get("about_me"): parts.append(f"About: {a}")
            
        return ". ".join(parts)

ranker = RankerService()
