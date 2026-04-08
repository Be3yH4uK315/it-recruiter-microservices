from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

try:
    from elasticsearch import AsyncElasticsearch
    from elasticsearch.exceptions import NotFoundError
except ModuleNotFoundError:  # pragma: no cover - env-dependent import
    AsyncElasticsearch = Any  # type: ignore[assignment]

    class NotFoundError(Exception):
        pass


from app.application.search.services.currency import normalize_to_rub
from app.domain.search.repository import LexicalSearchRepository

_REMOTE = "remote"
_ONSITE = "onsite"
_HYBRID = "hybrid"


@dataclass(slots=True)
class ElasticsearchCandidateRepository(LexicalSearchRepository):
    client: AsyncElasticsearch
    index_alias: str

    async def startup(self) -> None:
        await self._ensure_index()

    async def shutdown(self) -> None:
        await self.client.close()

    async def clear_all(self) -> None:
        await self.client.indices.delete(
            index=self.index_alias,
            ignore_unavailable=True,
        )
        await self._ensure_index()

    async def list_candidate_ids(self) -> list[str]:
        response = await self.client.search(
            index=self.index_alias,
            query={"match_all": {}},
            size=1000,
            _source=False,
            stored_fields=[],
            scroll="1m",
            sort=["_doc"],
        )

        candidate_ids: list[str] = []
        scroll_id = response.get("_scroll_id")

        try:
            while True:
                hits = response.get("hits", {}).get("hits", [])
                if not hits:
                    break

                candidate_ids.extend(str(hit["_id"]) for hit in hits if hit.get("_id") is not None)

                if not scroll_id:
                    break

                response = await self.client.scroll(
                    scroll_id=scroll_id,
                    scroll="1m",
                )
                scroll_id = response.get("_scroll_id")
        finally:
            if scroll_id:
                await self.client.clear_scroll(scroll_id=scroll_id, ignore=(404,))

        return candidate_ids

    async def search_candidate_ids(self, *, filters: dict, limit: int) -> list[str]:
        query = self._build_es_query(filters)
        response = await self.client.search(
            index=self.index_alias,
            query=query,
            size=limit,
            _source=False,
            stored_fields=[],
            track_total_hits=False,
        )
        return [str(hit["_id"]) for hit in response["hits"]["hits"]]

    async def count_candidates(self, *, filters: dict) -> int:
        query = self._build_es_query(filters)
        response = await self.client.count(
            index=self.index_alias,
            query=query,
        )
        return int(response.get("count", 0))

    async def get_documents(self, candidate_ids: list[str]) -> list[dict]:
        if not candidate_ids:
            return []

        response = await self.client.mget(
            index=self.index_alias,
            body={"ids": candidate_ids},
        )

        docs_by_id: dict[str, dict[str, Any]] = {}
        for item in response["docs"]:
            if not item.get("found"):
                continue

            source = dict(item["_source"])
            source["id"] = str(item["_id"])
            docs_by_id[str(item["_id"])] = source

        return [
            docs_by_id[candidate_id] for candidate_id in candidate_ids if candidate_id in docs_by_id
        ]

    async def get_document(self, candidate_id: UUID) -> dict | None:
        try:
            response = await self.client.get(
                index=self.index_alias,
                id=str(candidate_id),
            )
        except NotFoundError:
            return None

        if not response.get("found"):
            return None

        source = dict(response["_source"])
        source["id"] = str(candidate_id)
        return source

    async def upsert_document(self, *, candidate_id: UUID, document: dict) -> None:
        await self.client.index(
            index=self.index_alias,
            id=str(candidate_id),
            document=document,
            refresh=False,
        )

    async def delete_document(self, *, candidate_id: UUID) -> None:
        try:
            await self.client.delete(
                index=self.index_alias,
                id=str(candidate_id),
                refresh=False,
            )
        except NotFoundError:
            return

    async def _ensure_index(self) -> None:
        exists = await self.client.indices.exists(index=self.index_alias)
        if exists:
            return

        await self.client.indices.create(
            index=self.index_alias,
            mappings={
                "properties": {
                    "display_name": {"type": "text"},
                    "headline_role": {"type": "text"},
                    "location": {"type": "text"},
                    "work_modes": {"type": "keyword"},
                    "experience_years": {"type": "float"},
                    "skills": {
                        "type": "nested",
                        "properties": {
                            "skill": {"type": "keyword"},
                            "level": {"type": "integer"},
                            "kind": {"type": "keyword"},
                        },
                    },
                    "salary_min": {"type": "integer"},
                    "salary_max": {"type": "integer"},
                    "salary_min_rub": {"type": "float"},
                    "salary_max_rub": {"type": "float"},
                    "currency": {"type": "keyword"},
                    "english_level": {"type": "keyword"},
                    "about_me": {"type": "text"},
                    "searchable_text": {"type": "text"},
                    "status": {"type": "keyword"},
                }
            },
        )

    def _build_es_query(self, filters: dict[str, Any]) -> dict[str, Any]:
        must: list[dict[str, Any]] = []
        should: list[dict[str, Any]] = []
        must_not: list[dict[str, Any]] = []
        filter_clauses: list[dict[str, Any]] = []

        filter_clauses.append({"term": {"status": "active"}})

        role = str(filters.get("role") or "").strip()
        if role:
            must.append(
                {
                    "multi_match": {
                        "query": role,
                        "fields": [
                            "headline_role^4",
                            "searchable_text^2",
                            "about_me",
                        ],
                    }
                }
            )

        must_skills = filters.get("must_skills") or []
        nice_skills = filters.get("nice_skills") or []

        for skill_obj in must_skills:
            if not isinstance(skill_obj, dict):
                continue

            skill = str(skill_obj.get("skill") or "").strip().lower()
            if not skill:
                continue

            nested_must: list[dict[str, Any]] = [{"term": {"skills.skill": skill}}]
            level = skill_obj.get("level")
            if level is not None:
                nested_must.append({"range": {"skills.level": {"gte": int(level)}}})

            filter_clauses.append(
                {
                    "nested": {
                        "path": "skills",
                        "query": {
                            "bool": {
                                "must": nested_must,
                            }
                        },
                    }
                }
            )

        for skill_obj in nice_skills:
            if not isinstance(skill_obj, dict):
                continue

            skill = str(skill_obj.get("skill") or "").strip().lower()
            if not skill:
                continue

            nested_must: list[dict[str, Any]] = [{"term": {"skills.skill": skill}}]
            level = skill_obj.get("level")
            if level is not None:
                nested_must.append({"range": {"skills.level": {"gte": int(level)}}})

            should.append(
                {
                    "nested": {
                        "path": "skills",
                        "query": {
                            "bool": {
                                "must": nested_must,
                            }
                        },
                        "score_mode": "avg",
                    }
                }
            )

        requested_modes = self._normalize_work_modes(filters.get("work_modes") or [])
        compatible_modes = self._resolve_compatible_work_modes(requested_modes)
        if compatible_modes:
            filter_clauses.append({"terms": {"work_modes": compatible_modes}})

        location = str(filters.get("location") or "").strip()
        if location:
            if requested_modes == {_ONSITE}:
                should.append({"match": {"location": {"query": location, "boost": 3.0}}})
            elif requested_modes == {_HYBRID}:
                should.append({"match": {"location": {"query": location, "boost": 1.5}}})
            elif requested_modes == {_REMOTE}:
                pass
            else:
                should.append({"match": {"location": {"query": location, "boost": 2.0}}})

        experience_min = filters.get("experience_min")
        experience_max = filters.get("experience_max")
        exp_range: dict[str, float] = {}
        if experience_min is not None:
            exp_range["gte"] = float(experience_min)
        if experience_max is not None:
            exp_range["lte"] = float(experience_max) + 2.0
        if exp_range:
            filter_clauses.append({"range": {"experience_years": exp_range}})

        salary_min = filters.get("salary_min")
        salary_max = filters.get("salary_max")
        currency = filters.get("currency")

        if salary_min is not None:
            salary_min_rub = normalize_to_rub(salary_min, currency)
            if salary_min_rub is not None:
                filter_clauses.append(
                    {
                        "bool": {
                            "should": [
                                {"range": {"salary_max_rub": {"gte": salary_min_rub}}},
                                {"range": {"salary_min_rub": {"gte": salary_min_rub}}},
                                {"bool": {"must_not": {"exists": {"field": "salary_min_rub"}}}},
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                )

        if salary_max is not None:
            salary_max_rub = normalize_to_rub(salary_max, currency)
            if salary_max_rub is not None:
                filter_clauses.append(
                    {
                        "bool": {
                            "should": [
                                {"range": {"salary_min_rub": {"lte": salary_max_rub}}},
                                {"bool": {"must_not": {"exists": {"field": "salary_min_rub"}}}},
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                )

        english_level = str(filters.get("english_level") or "").strip().upper()
        if english_level:
            should.append({"term": {"english_level": {"value": english_level, "boost": 1.5}}})

        about_me = str(filters.get("about_me") or "").strip()
        if about_me:
            should.append(
                {
                    "match": {
                        "about_me": {
                            "query": about_me,
                            "boost": 1.5,
                        }
                    }
                }
            )
            should.append(
                {
                    "match": {
                        "searchable_text": {
                            "query": about_me,
                            "boost": 1.0,
                        }
                    }
                }
            )

        exclude_ids = filters.get("exclude_ids") or []
        if exclude_ids:
            must_not.append({"terms": {"_id": [str(value) for value in exclude_ids]}})

        bool_query: dict[str, Any] = {
            "must": must,
            "should": should,
            "filter": filter_clauses,
            "must_not": must_not,
        }

        return {"bool": bool_query}

    @staticmethod
    def _normalize_work_modes(items: list[Any]) -> set[str]:
        result: set[str] = set()

        for item in items:
            value = str(item).strip().lower()
            if not value:
                continue
            if value == "office":
                value = _ONSITE
            result.add(value)

        return result

    @staticmethod
    def _resolve_compatible_work_modes(requested_modes: set[str]) -> list[str]:
        if not requested_modes:
            return []

        compatible: set[str] = set()

        if _REMOTE in requested_modes:
            compatible.update({_REMOTE, _HYBRID})

        if _ONSITE in requested_modes:
            compatible.update({_ONSITE, _HYBRID})

        if _HYBRID in requested_modes:
            compatible.update({_HYBRID, _ONSITE, _REMOTE})

        return sorted(compatible)
