"""Summarize a results file as Markdown and as a self-contained HTML page."""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckStats:
    name: str
    kind: str
    passed: int = 0
    failed: int = 0
    no_verdict: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.no_verdict

    @property
    def pass_rate(self) -> float | None:
        d = self.passed + self.failed
        return self.passed / d if d else None


@dataclass
class Summary:
    n_traces: int
    overall_passed: int
    overall_failed: int
    overall_no_verdict: int
    checks: list[CheckStats]
    failures: list[tuple[str, list[str]]] = field(default_factory=list)  # (trace_id, failed checks)

    @property
    def pass_rate(self) -> float | None:
        d = self.overall_passed + self.overall_failed
        return self.overall_passed / d if d else None


def summarize(results: list[dict[str, Any]]) -> Summary:
    stats: dict[str, CheckStats] = {}
    failures: list[tuple[str, list[str]]] = []
    op = of = on = 0
    for rec in results:
        failed_here: list[str] = []
        for name, chk in rec.get("checks", {}).items():
            s = stats.setdefault(name, CheckStats(name, chk.get("kind", "?")))
            v = chk.get("passed")
            if v is True:
                s.passed += 1
            elif v is False:
                s.failed += 1
                failed_here.append(name)
            else:
                s.no_verdict += 1
        v = rec.get("passed")
        op += v is True
        of += v is False
        on += v is None
        if failed_here:
            failures.append((rec["trace_id"], failed_here))
    ordered = sorted(stats.values(), key=lambda s: (-(s.failed), s.name))
    return Summary(len(results), op, of, on, ordered, failures)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def to_markdown(summary: Summary, title: str = "Eval report") -> str:
    lines = [f"# {title}", "",
             f"Traces: **{summary.n_traces}** · Overall pass rate: **{_pct(summary.pass_rate)}** "
             f"({summary.overall_passed} pass, {summary.overall_failed} fail, "
             f"{summary.overall_no_verdict} no verdict)", "",
             "| Check | Kind | Pass rate | Pass | Fail | No verdict |", "|---|---|---|---|---|---|"]
    for s in summary.checks:
        lines.append(f"| {s.name} | {s.kind} | {_pct(s.pass_rate)} | {s.passed} | {s.failed} | {s.no_verdict} |")
    if summary.failures:
        lines += ["", "## Failing traces", "", "| Trace | Failed checks |", "|---|---|"]
        lines += [f"| {tid} | {', '.join(names)} |" for tid, names in summary.failures]
    return "\n".join(lines) + "\n"


_CSS = """body{font:15px/1.5 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222}
table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left}
th{background:#f4f4f4}.fail{color:#b00020}.pass{color:#0a7a2f}code{background:#f4f4f4;padding:0 .2rem}
@media (prefers-color-scheme:dark){body{background:#111;color:#ddd}th{background:#222}th,td{border-color:#333}}"""


def to_html(summary: Summary, title: str = "Eval report") -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(s.name)}</td><td>{e(s.kind)}</td><td>{_pct(s.pass_rate)}</td>"
        f"<td class='pass'>{s.passed}</td><td class='fail'>{s.failed}</td><td>{s.no_verdict}</td></tr>"
        for s in summary.checks)
    fails = "".join(f"<tr><td><code>{e(t)}</code></td><td>{e(', '.join(n))}</td></tr>"
                    for t, n in summary.failures)
    fail_html = (f"<h2>Failing traces</h2><table><tr><th>Trace</th><th>Failed checks</th></tr>{fails}</table>"
                 if summary.failures else "<p>No failing traces.</p>")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(title)}</title>"
            f"<style>{_CSS}</style></head><body><h1>{e(title)}</h1>"
            f"<p>Traces: <b>{summary.n_traces}</b> · Overall pass rate: <b>{_pct(summary.pass_rate)}</b> "
            f"({summary.overall_passed} pass, {summary.overall_failed} fail, {summary.overall_no_verdict} no verdict)</p>"
            f"<table><tr><th>Check</th><th>Kind</th><th>Pass rate</th><th>Pass</th><th>Fail</th><th>No verdict</th></tr>"
            f"{rows}</table>{fail_html}</body></html>\n")
