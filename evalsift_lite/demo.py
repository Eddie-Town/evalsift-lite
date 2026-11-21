"""Offline demo: grade a fake support agent's traces and write report.html.

    pip install -e .
    python -m evalsift_lite.demo            # writes ./report.html and ./report.md
    python -m evalsift_lite.demo --out-dir out --traces my_traces.jsonl

No API key, no network. Uses data/demo/traces.jsonl when run from a source
checkout; otherwise regenerates the same traces with the fake agent.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from .fake_model import demo_traces
from .graders import GradeResult
from .report import summarize, to_html, to_markdown
from .runner import build_graders, run, write_results
from .traces import Trace, TraceValidationError, load_traces, write_traces

DEMO_GRADERS = [
    {"type": "no_tool_errors"},
    {"type": "not_contains", "name": "no_refusal", "value": "cannot help"},
    {"type": "max_steps", "name": "no_tool_loop", "limit": 4},
]
REPO_DATA = Path(__file__).resolve().parent.parent / "data" / "demo" / "traces.jsonl"


def order_number_needs_lookup(trace: Trace) -> GradeResult:
    """Custom grader example: an order number in the reply must come from a lookup_order call."""
    mentioned = set(re.findall(r"#(\d{4})", trace.output_text()))
    looked_up = {str(s.args.get("order_id")) for s in trace.tool_calls() if s.name == "lookup_order"}
    invented = sorted(mentioned - looked_up)
    return GradeResult("order_numbers_are_looked_up", not invented,
                       f"order(s) {invented} never looked up" if invented else "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evalsift_lite.demo", description=__doc__.splitlines()[0])
    ap.add_argument("--traces", type=Path, help="traces.jsonl to grade (default: bundled demo traces)")
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    ap.add_argument("--regenerate", action="store_true", help="rewrite data/demo/traces.jsonl from the fake agent")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()

    if a.regenerate:
        REPO_DATA.parent.mkdir(parents=True, exist_ok=True)
        print(f"wrote {write_traces(demo_traces(), REPO_DATA)} traces to {REPO_DATA}")
    path = a.traces or (REPO_DATA if REPO_DATA.exists() else None)
    try:
        traces = load_traces(path) if path else demo_traces()
    except TraceValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    results = run(traces, [*build_graders(DEMO_GRADERS), order_number_needs_lookup], run_id="demo")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    write_results(results, a.out_dir / "results.jsonl")
    s = summarize(results)
    title = "evalsift-lite demo: fake support agent"
    (a.out_dir / "report.md").write_text(to_markdown(s, title), encoding="utf-8")
    (a.out_dir / "report.html").write_text(to_html(s, title), encoding="utf-8")
    rate = "n/a" if s.pass_rate is None else f"{s.pass_rate:.0%}"
    print(f"graded {s.n_traces} traces from {path or 'the built-in fake agent'}: pass rate {rate}, "
          f"{len(s.failures)} failing")
    for tid, names in s.failures:
        print(f"  {tid}: {', '.join(names)}")
    print(f"wrote {a.out_dir / 'report.html'} in {time.perf_counter() - t0:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
