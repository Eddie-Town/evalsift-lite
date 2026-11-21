"""Run code graders over traces and write results JSONL (lite: no LLM judges)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable

from .graders import Grader, build_grader
from .traces import Trace


def build_graders(specs: list[dict[str, Any]]) -> list[Grader]:
    return [build_grader(s) for s in specs]


def overall(checks: dict[str, dict[str, Any]]) -> bool | None:
    values = [c.get("passed") for c in checks.values()]
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def run(traces: Iterable[Trace], graders: list[Grader], run_id: str | None = None) -> list[dict[str, Any]]:
    """Apply every grader to every trace. Returns result records."""
    rid = run_id or time.strftime("run-%Y%m%d-%H%M%S")
    results: list[dict[str, Any]] = []
    for trace in traces:
        rec: dict[str, dict[str, Any]] = {}
        for g in graders:
            r = g(trace)
            if r.name in rec:
                raise ValueError(f"two graders share the name {r.name!r}; give one a 'name'")
            rec[r.name] = r.to_dict()
        results.append({"trace_id": trace.trace_id, "passed": overall(rec), "run_id": rid, "checks": rec})
    return results


def write_results(results: Iterable[dict[str, Any]], path: str | Path) -> int:
    n = 0
    with Path(path).open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n
