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
        description="Evaluate lexical, vector and hybrid search quality on a control dataset.",
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to JSON file with control queries and relevance judgments.",
    )
    parser.add_argument(
        "--mode",
        dest="modes",
        action="append",
        choices=[item.value for item in SearchEvaluationMode],
        help="Evaluation mode. Can be specified multiple times. Defaults to lexical, vector, hybrid.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save JSON report.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset).resolve()
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    k_values, cases = load_quality_cases(payload)

    if not cases:
        raise ValueError("dataset must contain at least one evaluation case")

    modes = (
        [SearchEvaluationMode(item) for item in args.modes]
        if args.modes
        else [
            SearchEvaluationMode.LEXICAL,
            SearchEvaluationMode.VECTOR,
            SearchEvaluationMode.HYBRID,
        ]
    )

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
        report = await evaluator.evaluate(
            cases=cases,
            k_values=k_values,
            modes=modes,
        )
    finally:
        await registry.shutdown()
        await http_client.aclose()

    report_json = json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    )

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.write_text(report_json, encoding="utf-8")
    else:
        print(report_json)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
