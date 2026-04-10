from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from app.application.search.services.quality_evaluation import (
    SearchEvaluationMode,
    SearchQualityEvaluator,
    load_quality_cases,
)
from app.config import get_settings
from app.infrastructure.integrations.http_client import build_default_async_http_client
from app.infrastructure.integrations.resource_registry import ResourceRegistry
from app.infrastructure.observability.logger import configure_logging

ROOT_DIR = Path(__file__).resolve().parents[1]
os.chdir(ROOT_DIR)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview ranked candidates for one quality-evaluation case.",
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to JSON file with evaluation cases.",
    )
    parser.add_argument(
        "--case-id",
        required=True,
        help="Identifier of the case to preview.",
    )
    parser.add_argument(
        "--mode",
        choices=[item.value for item in SearchEvaluationMode],
        default=SearchEvaluationMode.HYBRID.value,
        help="Search mode to preview.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of candidates to show.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    payload = json.loads(Path(args.dataset).resolve().read_text(encoding="utf-8"))
    _, cases = load_quality_cases(payload)

    target_case = next((item for item in cases if item.case_id == args.case_id), None)
    if target_case is None:
        raise ValueError(f"case '{args.case_id}' not found in dataset")

    settings = get_settings()
    configure_logging(settings)

    http_client = build_default_async_http_client(settings)
    registry = ResourceRegistry(
        settings=settings,
        http_client=http_client,
    )

    try:
        await registry.startup()

        evaluator = SearchQualityEvaluator(
            lexical_repository=registry.require_lexical_repository(),
            vector_repository=registry.require_vector_repository(),
            embedding_provider=registry.require_embedding_provider(),
            hybrid_search_service=registry.require_hybrid_search_service(),
        )
        await evaluator.warmup(
            cases=[target_case],
            modes=[SearchEvaluationMode(args.mode)],
            limit=args.limit,
        )
        documents = await evaluator.search_documents(
            mode=SearchEvaluationMode(args.mode),
            filters=target_case.filters,
            limit=args.limit,
        )
    finally:
        await registry.shutdown()
        await http_client.aclose()

    result = {
        "case_id": target_case.case_id,
        "mode": args.mode,
        "limit": args.limit,
        "items": [
            {
                "id": str(item.get("id") or ""),
                "display_name": item.get("display_name"),
                "headline_role": item.get("headline_role"),
                "location": item.get("location"),
                "experience_years": item.get("experience_years"),
                "skills": item.get("skills"),
                "match_score": item.get("match_score"),
            }
            for item in documents
        ],
    }

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
