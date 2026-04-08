from __future__ import annotations


class SearchDomainError(Exception):
    pass


class InvalidSearchFilterError(SearchDomainError):
    pass


class CandidateDocumentNotFoundError(SearchDomainError):
    pass


class SearchBackendUnavailableError(SearchDomainError):
    pass


class EmbeddingGenerationError(SearchDomainError):
    pass


class RankingUnavailableError(SearchDomainError):
    pass
