from __future__ import annotations


def reciprocal_rank_fusion(
    *,
    ranked_lists: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    if k < 1:
        raise ValueError("k must be >= 1")

    scores: dict[str, float] = {}
    best_rank: dict[str, int] = {}

    for ranked in ranked_lists:
        seen_in_list: set[str] = set()

        for rank, candidate_id in enumerate(ranked):
            if not candidate_id or candidate_id in seen_in_list:
                continue

            seen_in_list.add(candidate_id)
            scores[candidate_id] = scores.get(candidate_id, 0.0) + (1.0 / (k + rank + 1))

            current_best_rank = best_rank.get(candidate_id)
            if current_best_rank is None or rank < current_best_rank:
                best_rank[candidate_id] = rank

    return sorted(
        scores.items(),
        key=lambda item: (-item[1], best_rank.get(item[0], 10**9), item[0]),
    )
