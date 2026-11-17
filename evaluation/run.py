"""python -m evaluation.run [--live] [--output reports/evaluation.json]."""

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from app.model import ModelError, generate
from app.reviews import validate_locations
from evaluation.dataset import cases


def score_case(expected, findings):
    remaining = list(expected)
    matched = 0
    for finding in findings:
        match = next(
            (
                item
                for item in remaining
                if item["file"] == finding["file"]
                and finding["line"] in item["lines"]
                and item["category"] == finding["category"]
            ),
            None,
        )
        if match:
            remaining.remove(match)
            matched += 1
    return {"tp": matched, "fp": len(findings) - matched, "fn": len(remaining)}


def aggregate(rows, mode):
    tp = sum(r["score"]["tp"] for r in rows)
    fp = sum(r["score"]["fp"] for r in rows)
    fn = sum(r["score"]["fn"] for r in rows)
    return {
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(rows),
        "location_category_precision": tp / (tp + fp) if tp + fp else None,
        "location_category_recall": tp / (tp + fn) if tp + fn else None,
        "failed_cases": sum(r["error"] is not None for r in rows),
        "invalid_location_findings": sum(r["invalid_locations"] for r in rows),
        "total_findings": sum(len(r["findings"]) for r in rows),
        "median_latency_seconds": statistics.median(r["duration_seconds"] for r in rows)
        if rows
        else None,
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "results": rows,
    }


async def evaluate(live=False, limit=None):
    rows = []
    for case in list(cases())[:limit]:
        started = time.monotonic()
        findings, prompt, completion, error, invalid = [], 0, 0, None, 0
        model = prompt_version = None
        try:
            if live:
                for attempt in range(3):
                    try:
                        response = await generate(case["diff"])
                        break
                    except ModelError as exc:
                        if not exc.retryable or attempt == 2:
                            raise
                        await asyncio.sleep(exc.retry_after)
                findings, prompt, completion = (
                    response.findings,
                    response.prompt_tokens,
                    response.completion_tokens,
                )
                model, prompt_version = response.model, response.prompt_version
                for finding in findings:
                    try:
                        validate_locations([finding], case["diff"])
                    except ValueError:
                        invalid += 1
        except Exception as exc:
            error = exc.reason if isinstance(exc, ModelError) else type(exc).__name__
        row = {
            **case,
            "findings": findings,
            "score": score_case(case["expected"], findings),
            "error": error,
            "invalid_locations": invalid,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "model": model,
            "prompt_version": prompt_version,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        rows.append(row)
        if live:
            print(f"{case['id']}: {error or 'completed'}", flush=True)
    report = aggregate(rows, "live" if live else "dry-run-empty-baseline")
    report["dataset_sha256"] = hashlib.sha256(
        json.dumps(list(cases()), sort_keys=True).encode()
    ).hexdigest()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call Groq; consumes API credits")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", default="reports/evaluation.json")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    report = asyncio.run(evaluate(args.live, args.limit))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    raise SystemExit(1 if report["failed_cases"] else 0)


if __name__ == "__main__":
    main()
