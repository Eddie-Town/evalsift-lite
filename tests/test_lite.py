import json
from pathlib import Path

from evalsift_lite.demo import REPO_DATA, main
from evalsift_lite.fake_model import demo_traces, fake_agent
from evalsift_lite.graders import no_tool_errors
from evalsift_lite.traces import load_traces


def test_fake_agent_is_deterministic() -> None:
    assert fake_agent("x", "Where is order 1001?") == fake_agent("x", "Where is order 1001?")


def test_bundled_traces_match_fake_agent() -> None:
    assert load_traces(REPO_DATA) == demo_traces()


def test_demo_writes_report(tmp_path: Path) -> None:
    assert main(["--out-dir", str(tmp_path)]) == 0
    html = (tmp_path / "report.html").read_text()
    assert html.startswith("<!doctype html>") and "demo-04" in html
    results = [json.loads(l) for l in (tmp_path / "results.jsonl").read_text().splitlines()]
    failing = {r["trace_id"] for r in results if not r["passed"]}
    # every planted failure is caught, and nothing else
    planted = {t.trace_id for t in demo_traces() if t.metadata["planted_failure"]}
    assert failing == planted


def test_tool_error_grader() -> None:
    t = fake_agent("x", "Where is order 9999?")
    assert not no_tool_errors()(t).passed
