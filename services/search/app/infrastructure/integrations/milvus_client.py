from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

try:
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent import
    Collection = Any  # type: ignore[assignment]
    CollectionSchema = Any  # type: ignore[assignment]
    DataType = Any  # type: ignore[assignment]
    FieldSchema = Any  # type: ignore[assignment]
    connections = None
    utility = None
    _PYMILVUS_IMPORT_ERROR = exc
else:
    _PYMILVUS_IMPORT_ERROR = None

from app.domain.search.errors import SearchBackendUnavailableError


@dataclass(slots=True)
class MilvusClientWrapper:
    host: str
    port: int
    collection_name: str
    dimension: int
    alias: str = "default"
    collection: Collection | None = field(default=None, init=False)

    async def startup(self) -> None:
        if _PYMILVUS_IMPORT_ERROR is not None:
            raise SearchBackendUnavailableError(
                "pymilvus dependency is not installed"
            ) from _PYMILVUS_IMPORT_ERROR
        try:
            await asyncio.to_thread(
                connections.connect,
                self.alias,
                host=self.host,
                port=str(self.port),
            )
            await asyncio.to_thread(self._ensure_collection)
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus startup failed") from exc

    async def shutdown(self) -> None:
        try:
            await asyncio.to_thread(connections.disconnect, self.alias)
        except Exception:
            return

    async def reset_collection(self) -> None:
        if _PYMILVUS_IMPORT_ERROR is not None:
            raise SearchBackendUnavailableError(
                "pymilvus dependency is not installed"
            ) from _PYMILVUS_IMPORT_ERROR

        def _sync_reset() -> None:
            if utility.has_collection(self.collection_name, using=self.alias):
                utility.drop_collection(self.collection_name, using=self.alias)
            self.collection = None
            self._ensure_collection()

        try:
            await asyncio.to_thread(_sync_reset)
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus reset collection failed") from exc

    async def insert(self, ids: list[str], vectors: list[list[float]]) -> None:
        if not ids or not vectors:
            return

        def _sync_insert() -> None:
            if self.collection is None:
                raise SearchBackendUnavailableError("milvus collection is not initialized")

            self.collection.upsert([ids, vectors])
            self.collection.flush()

        try:
            await asyncio.to_thread(_sync_insert)
        except SearchBackendUnavailableError:
            raise
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus insert failed") from exc

    async def delete(self, candidate_id: str) -> None:
        def _sync_delete() -> None:
            if self.collection is None:
                raise SearchBackendUnavailableError("milvus collection is not initialized")

            expr = f'candidate_id == "{candidate_id}"'
            self.collection.delete(expr)
            self.collection.flush()

        try:
            await asyncio.to_thread(_sync_delete)
        except SearchBackendUnavailableError:
            raise
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus delete failed") from exc

    async def has_vector(self, candidate_id: str) -> bool:
        def _sync_has_vector() -> bool:
            if self.collection is None:
                raise SearchBackendUnavailableError("milvus collection is not initialized")

            results = self.collection.query(
                expr=f'candidate_id == "{candidate_id}"',
                output_fields=["candidate_id"],
                limit=1,
            )
            return bool(results)

        try:
            return await asyncio.to_thread(_sync_has_vector)
        except SearchBackendUnavailableError:
            raise
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus has_vector failed") from exc

    async def healthcheck(self) -> None:
        def _sync_healthcheck() -> None:
            if self.collection is None:
                raise SearchBackendUnavailableError("milvus collection is not initialized")

            _ = self.collection.num_entities

        try:
            await asyncio.to_thread(_sync_healthcheck)
        except SearchBackendUnavailableError:
            raise
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus healthcheck failed") from exc

    async def list_candidate_ids(self) -> list[str]:
        def _sync_list_candidate_ids() -> list[str]:
            if self.collection is None:
                raise SearchBackendUnavailableError("milvus collection is not initialized")

            limit = max(int(getattr(self.collection, "num_entities", 0) or 0), 1)
            results = self.collection.query(
                expr='candidate_id != ""',
                output_fields=["candidate_id"],
                limit=limit,
            )
            return [
                str(item["candidate_id"])
                for item in results
                if isinstance(item, dict) and item.get("candidate_id") is not None
            ]

        try:
            return await asyncio.to_thread(_sync_list_candidate_ids)
        except SearchBackendUnavailableError:
            raise
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus list_candidate_ids failed") from exc

    async def search(
        self,
        *,
        query_vector: list[float],
        exclude_ids: list[str],
        top_k: int,
    ) -> list[dict]:
        if not query_vector or top_k <= 0:
            return []

        def _sync_search() -> list[dict]:
            if self.collection is None:
                raise SearchBackendUnavailableError("milvus collection is not initialized")

            safe_ids = exclude_ids[:1000]
            expr = None
            if safe_ids:
                ids_list_str = ", ".join(f'"{value}"' for value in safe_ids)
                expr = f"candidate_id not in [{ids_list_str}]"

            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
            results = self.collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k + len(safe_ids),
                expr=expr,
                output_fields=["candidate_id"],
            )

            hits: list[dict] = []
            exclude_set = set(safe_ids)

            if results and results[0]:
                for hit in results[0]:
                    candidate_id = str(hit.id)
                    if candidate_id in exclude_set:
                        continue

                    hits.append(
                        {
                            "candidate_id": candidate_id,
                            "vector_score": float(hit.distance),
                        }
                    )

                    if len(hits) >= top_k:
                        break

            return hits

        try:
            return await asyncio.to_thread(_sync_search)
        except SearchBackendUnavailableError:
            raise
        except Exception as exc:
            raise SearchBackendUnavailableError("milvus search failed") from exc

    def _ensure_collection(self) -> None:
        if utility.has_collection(self.collection_name, using=self.alias):
            self.collection = Collection(self.collection_name, using=self.alias)
            self.collection.load()
            return

        fields = [
            FieldSchema(
                name="candidate_id",
                dtype=DataType.VARCHAR,
                max_length=36,
                is_primary=True,
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.dimension,
            ),
        ]
        schema = CollectionSchema(fields, description="Candidate embeddings")

        self.collection = Collection(
            name=self.collection_name,
            schema=schema,
            using=self.alias,
        )

        self.collection.create_index(
            field_name="embedding",
            index_params={
                "metric_type": "IP",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            },
        )
        self.collection.load()
