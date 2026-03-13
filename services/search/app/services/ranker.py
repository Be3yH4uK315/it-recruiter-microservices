from typing import Any

import numpy as np
import structlog

from app.core.config import settings
from app.core.resources import resources
from app.models.search import SearchFilters
from app.utils.currency import normalize_to_rub

logger = structlog.get_logger()


class RankerService:
    async def rerank_candidates(
        self, query_text: str, candidates: list[dict[str, Any]], filters: SearchFilters
    ) -> list[dict[str, Any]]:

        if not candidates:
            return []

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
        self, candidate: dict, filters: SearchFilters, ml_score: float
    ) -> tuple[float, dict]:
        """
        Multiplicative Scoring Model:
        Score = ML_Prob * SkillFactor * ExpFactor * LocFactor * SalFactor * EngFactor
        """
        factors = {"ml_score": round(ml_score, 4)}

        req_skills = filters.must_skills + (filters.nice_skills or [])
        cand_skills = candidate.get("skills", [])
        cand_skill_map = {
            s["skill"]: s.get("level", 3) if isinstance(s, dict) else 3 
            for s in cand_skills
        }
        
        skill_factor = 1.0
        if req_skills:
            match_count = 0
            penalty = 0.0
            for rs in req_skills:
                skill_name = rs["skill"]
                req_lvl = rs.get("level", 3)
                if skill_name in cand_skill_map:
                    match_count += 1
                    cand_lvl = cand_skill_map[skill_name]
                    if cand_lvl < req_lvl:
                        penalty += (req_lvl - cand_lvl) * 0.15
            
            coverage = match_count / len(req_skills)
            skill_factor = coverage * (1.0 - penalty)
            skill_factor = max(settings.FACTOR_NO_SKILLS, skill_factor)
        
        factors["skill_factor"] = round(skill_factor, 2)

        exp_factor = 1.0
        cand_exp = candidate.get("experience_years", 0)
        req_min_exp = filters.experience_min or 0
        if cand_exp < req_min_exp:
            diff = req_min_exp - cand_exp
            exp_factor = max(settings.FACTOR_EXP_MISMATCH, 1.0 - (diff * 0.2))
        factors["exp_factor"] = round(exp_factor, 2)

        loc_factor = settings.FACTOR_LOCATION_MATCH
        req_loc = (filters.location or "").lower()
        cand_loc = (candidate.get("location") or "").lower()
        is_city_match = (req_loc == cand_loc) and bool(req_loc)

        req_modes = filters.work_modes or []
        cand_modes = candidate.get("work_modes") or []

        is_remote_req = "remote" in [m.lower() for m in req_modes]
        is_remote_cand = "remote" in [m.lower() for m in cand_modes]

        if is_city_match:
            loc_factor = 1.15 if is_remote_req and is_remote_cand else 1.0
        elif is_remote_req and (is_remote_cand or not cand_modes):
            loc_factor = 1.0
        
        factors["loc_factor"] = round(loc_factor, 2)

        sal_factor = 1.0
        cand_sal_rub = normalize_to_rub(candidate.get("salary_min"), candidate.get("currency"))
        emp_sal_rub = normalize_to_rub(filters.salary_max, filters.currency)

        if emp_sal_rub and cand_sal_rub:
            if cand_sal_rub <= emp_sal_rub:
                sal_factor = 1.0
            else:
                ratio = cand_sal_rub / emp_sal_rub
                sal_factor = max(0.6, 1.0 - ((ratio - 1.0) * 0.6))

        factors["sal_factor"] = round(sal_factor, 2)

        eng_factor = 1.0
        if filters.english_level:
            levels = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
            req_lvl = levels.get(filters.english_level.upper(), 0)
            cand_lvl_str = candidate.get("english_level")
            cand_lvl = levels.get(cand_lvl_str.upper() if cand_lvl_str else "", 0)

            if cand_lvl == 0:
                eng_factor = 0.9
            elif cand_lvl < req_lvl:
                diff = req_lvl - cand_lvl
                eng_factor = max(0.6, 1.0 - (diff * 0.15))
            elif cand_lvl > req_lvl:
                eng_factor = 1.05
        factors["eng_factor"] = round(eng_factor, 2)

        final_score = ml_score * skill_factor * exp_factor * loc_factor * sal_factor * eng_factor
        return round(final_score, 4), factors

    def _construct_candidate_text(self, cand: dict) -> str:
        parts = []
        if r := cand.get("headline_role"):
            parts.append(f"Role: {r}")
        
        skills = cand.get("skills", [])
        if skills:
            if isinstance(skills[0], dict):
                skill_names = ", ".join([s["skill"] for s in skills])
            else:
                skill_names = ", ".join(skills)
            parts.append(f"Skills: {skill_names}")
            
        if e := cand.get("experience_years"):
            parts.append(f"Experience: {e} years")
        
        experiences = cand.get("experiences", [])
        if experiences:
            exp_texts = []
            for exp in experiences:
                pos = exp.get("position", "")
                resp = exp.get("responsibilities", "")
                if pos or resp:
                    exp_texts.append(f"{pos}: {resp}")
            if exp_texts:
                parts.append("Work history: " + " | ".join(exp_texts))

        if ab := cand.get("about_me"):
            parts.append(f"About: {ab}")
            
        return ". ".join(parts)


ranker = RankerService()
