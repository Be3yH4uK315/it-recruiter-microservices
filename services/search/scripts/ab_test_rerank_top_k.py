from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from app.application.search.services.hybrid_search import DefaultHybridSearchService
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
        description="Compare hybrid search quality and latency for different rerank_top_k values.",
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to JSON file with control queries and relevance judgments.",
    )
    parser.add_argument(
        "--rerank-top-k",
        dest="rerank_top_k_values",
        action="append",
        type=int,
        required=True,
        help="rerank_top_k value to evaluate. Can be specified multiple times.",
    )
    parser.add_argument(
        "--include-baselines",
        action="store_true",
        help="Also evaluate lexical and vector baselines once.",
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

    rerank_top_k_values = sorted({value for value in args.rerank_top_k_values if value > 0})
    if not rerank_top_k_values:
        raise ValueError("at least one positive rerank_top_k value is required")

    settings = get_settings()
    configure_logging(settings)

    http_client = build_default_async_http_client(settings)
    registry = ResourceRegistry(
        settings=settings,
        http_client=http_client,
    )

    try:
        await registry.startup()

        result: dict[str, object] = {
            "k_values": k_values,
            "rerank_top_k_values": rerank_top_k_values,
            "baseline_summaries": [],
            "hybrid_variants": [],
        }

        if args.include_baselines:
            baseline_evaluator = SearchQualityEvaluator(
                lexical_repository=registry.require_lexical_repository(),
                vector_repository=registry.require_vector_repository(),
                embedding_provider=registry.require_embedding_provider(),
                hybrid_search_service=registry.require_hybrid_search_service(),
            )
            baseline_report = await baseline_evaluator.evaluate(
                cases=cases,
                k_values=k_values,
                modes=[
                    SearchEvaluationMode.LEXICAL,
                    SearchEvaluationMode.VECTOR,
                ],
            )
            result["baseline_summaries"] = [
                item.to_dict() for item in baseline_report.summaries
            ]

        for rerank_top_k in rerank_top_k_values:
            hybrid_service = DefaultHybridSearchService(
                lexical_repository=registry.require_lexical_repository(),
                vector_repository=registry.require_vector_repository(),
                embedding_provider=registry.require_embedding_provider(),
                ranker=registry.require_ranker(),
                retrieval_size=settings.retrieval_size,
                rerank_top_k=rerank_top_k,
                rrf_k=settings.rrf_k,
                result_cache_ttl_seconds=0.0,
                result_cache_size=settings.search_result_cache_size,
                timing_logging_enabled=settings.search_timing_logging_enabled,
                timing_logging_threshold_ms=settings.search_timing_logging_threshold_ms,
            )
            evaluator = SearchQualityEvaluator(
                lexical_repository=registry.require_lexical_repository(),
                vector_repository=registry.require_vector_repository(),
                embedding_provider=registry.require_embedding_provider(),
                hybrid_search_service=hybrid_service,
            )
            report = await evaluator.evaluate(
                cases=cases,
                k_values=k_values,
                modes=[SearchEvaluationMode.HYBRID],
            )
            result["hybrid_variants"].append(
                {
                    "rerank_top_k": rerank_top_k,
                    "summary": report.summaries[0].to_dict() if report.summaries else None,
                }
            )

    finally:
        await registry.shutdown()
        await http_client.aclose()

    report_json = json.dumps(
        result,
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
