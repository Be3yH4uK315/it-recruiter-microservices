from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.application.common.contracts import EmbeddingProvider
from app.domain.search.errors import EmbeddingGenerationError

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent import
    SentenceTransformer = None  # type: ignore[assignment]
    _SENTENCE_TRANSFORMERS_IMPORT_ERROR = exc
else:
    _SENTENCE_TRANSFORMERS_IMPORT_ERROR = None


@dataclass(slots=True)
class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    model_name: str
    concurrency_limit: int = 1
    _model: SentenceTransformer | None = field(default=None, init=False, repr=False)
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.concurrency_limit)

    async def startup(self) -> None:
        if self._model is not None:
            return
        if SentenceTransformer is None:
            raise EmbeddingGenerationError(
                "sentence-transformers dependency is not installed"
            ) from _SENTENCE_TRANSFORMERS_IMPORT_ERROR

        try:
            self._model = await asyncio.to_thread(SentenceTransformer, self.model_name)
        except Exception as exc:
            raise EmbeddingGenerationError("embedding model initialization failed") from exc

    async def shutdown(self) -> None:
        self._model = None

    async def encode_text(self, text: str) -> list[float]:
        normalized = text.strip()
        if not normalized:
            return []

        vectors = await self.encode_many([normalized])
        return vectors[0] if vectors else []

    async def encode_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self._model is None:
            raise EmbeddingGenerationError("embedding model is not initialized")

        normalized_texts: list[str] = []
        non_empty_positions: list[int] = []

        for idx, item in enumerate(texts):
            normalized = item.strip() if item else ""
            if not normalized:
                continue
            normalized_texts.append(normalized)
            non_empty_positions.append(idx)

        if not normalized_texts:
            return [[] for _ in texts]

        async with self._semaphore:
            try:
                vectors = await asyncio.to_thread(
                    self._model.encode,
                    normalized_texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
            except Exception as exc:
                raise EmbeddingGenerationError("embedding generation failed") from exc

        result: list[list[float]] = [[] for _ in texts]
        for idx, vector in zip(non_empty_positions, vectors, strict=False):
            if hasattr(vector, "tolist"):
                result[idx] = [float(value) for value in vector.tolist()]
            else:
                result[idx] = [float(value) for value in vector]

        return result
