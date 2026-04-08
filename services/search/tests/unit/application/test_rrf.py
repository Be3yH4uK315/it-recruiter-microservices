from __future__ import annotations

from app.application.search.services.rrf import reciprocal_rank_fusion


def test_rrf_returns_empty_for_empty_lists() -> None:
    result = reciprocal_rank_fusion(ranked_lists=[], k=60)
    assert result == []


def test_rrf_fuses_single_ranked_list_in_order() -> None:
    result = reciprocal_rank_fusion(
        ranked_lists=[["a", "b", "c"]],
        k=60,
    )

    assert [candidate_id for candidate_id, _ in result] == ["a", "b", "c"]
    assert result[0][1] > result[1][1] > result[2][1]


def test_rrf_combines_scores_from_multiple_ranked_lists() -> None:
    result = reciprocal_rank_fusion(
        ranked_lists=[
            ["a", "b", "c"],
            ["b", "a", "d"],
        ],
        k=60,
    )

    ids = [candidate_id for candidate_id, _ in result]
    assert ids[0] in {"a", "b"}
    assert ids[1] in {"a", "b"}
    assert ids[0] != ids[1]
    assert "c" in ids
    assert "d" in ids


def test_rrf_repeated_candidate_gets_higher_score_than_singletons() -> None:
    result = reciprocal_rank_fusion(
        ranked_lists=[
            ["a", "b"],
            ["a", "c"],
        ],
        k=60,
    )

    scores = {candidate_id: score for candidate_id, score in result}
    assert scores["a"] > scores["b"]
    assert scores["a"] > scores["c"]


def test_rrf_respects_rank_position() -> None:
    result = reciprocal_rank_fusion(
        ranked_lists=[
            ["x", "y"],
            ["x", "z"],
        ],
        k=60,
    )

    scores = {candidate_id: score for candidate_id, score in result}
    assert scores["x"] > scores["y"]
    assert scores["x"] > scores["z"]
