"""Load and validate ``traces.jsonl`` files.

One JSON object per line::

    {"trace_id": "t1", "input": "...", "output": "...",
     "steps": [{"type": "tool", "name": "lookup_order", "args": {...},
                "result": ..., "error": null}],
     "metadata": {...}}

``input`` and ``output`` may be any JSON value (usually a string).
``steps`` and ``metadata`` are optional. Every error message names the file
and line number so problems can be fixed by hand.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

STEP_TYPES = ("llm", "tool")
TOP_LEVEL_KEYS = {"trace_id", "input", "output", "steps", "metadata"}
STEP_KEYS = {"type", "name", "args", "result", "error"}


class TraceValidationError(ValueError):
    """Raised when a traces file has one or more invalid records."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        shown = "\n".join(errors[:20])
        more = f"\n... and {len(errors) - 20} more" if len(errors) > 20 else ""
        super().__init__(f"{len(errors)} validation error(s):\n{shown}{more}")


@dataclass
class Step:
    """One LLM call or tool call inside a trace."""

    type: str
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None


@dataclass
class Trace:
    """One end-to-end interaction with the system under test."""

    trace_id: str
    input: Any
    output: Any
    steps: list[Step] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def tool_calls(self) -> list[Step]:
        return [s for s in self.steps if s.type == "tool"]

    def output_text(self) -> str:
        return as_text(self.output)

    def input_text(self) -> str:
        return as_text(self.input)


def as_text(value: Any) -> str:
    """Render a JSON value as text: strings as-is, everything else as JSON."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_record(obj: Any, where: str) -> list[str]:
    """Return a list of human-readable problems with one parsed record."""
    errs: list[str] = []
    if not isinstance(obj, dict):
        return [f"{where}: expected a JSON object, got {type(obj).__name__}"]
    for key in ("trace_id", "input", "output"):
        if key not in obj:
            errs.append(f"{where}: missing required field '{key}'")
    tid = obj.get("trace_id")
    if "trace_id" in obj and (not isinstance(tid, str) or not tid.strip()):
        errs.append(f"{where}: 'trace_id' must be a non-empty string")
    unknown = set(obj) - TOP_LEVEL_KEYS
    if unknown:
        errs.append(f"{where}: unknown field(s) {sorted(unknown)}; put extra data in 'metadata'")
    if "metadata" in obj and not isinstance(obj["metadata"], dict):
        errs.append(f"{where}: 'metadata' must be an object")
    steps = obj.get("steps", [])
    if not isinstance(steps, list):
        errs.append(f"{where}: 'steps' must be a list")
        return errs
    for i, step in enumerate(steps):
        sw = f"{where} steps[{i}]"
        if not isinstance(step, dict):
            errs.append(f"{sw}: expected an object")
            continue
        if step.get("type") not in STEP_TYPES:
            errs.append(f"{sw}: 'type' must be one of {list(STEP_TYPES)}, got {step.get('type')!r}")
        if step.get("type") == "tool" and not step.get("name"):
            errs.append(f"{sw}: tool steps need a 'name'")
        if "name" in step and not isinstance(step["name"], str):
            errs.append(f"{sw}: 'name' must be a string")
        if "args" in step and step["args"] is not None and not isinstance(step["args"], dict):
            errs.append(f"{sw}: 'args' must be an object")
        if step.get("error") is not None and not isinstance(step["error"], str):
            errs.append(f"{sw}: 'error' must be a string or null")
        extra = set(step) - STEP_KEYS
        if extra:
            errs.append(f"{sw}: unknown field(s) {sorted(extra)}")
    return errs


def _to_trace(obj: dict[str, Any]) -> Trace:
    steps = [
        Step(
            type=s["type"],
            name=s.get("name", "") or "",
            args=s.get("args") or {},
            result=s.get("result"),
            error=s.get("error"),
        )
        for s in obj.get("steps", [])
    ]
    return Trace(
        trace_id=obj["trace_id"],
        input=obj["input"],
        output=obj["output"],
        steps=steps,
        metadata=obj.get("metadata") or {},
    )


def parse_lines(lines: Iterable[str], source: str = "<input>") -> tuple[list[Trace], list[str]]:
    """Parse JSONL lines. Returns (valid traces, error messages). Blank lines are skipped."""
    traces: list[Trace] = []
    errors: list[str] = []
    seen: dict[str, int] = {}
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        where = f"{source}:{lineno}"
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{where}: invalid JSON ({exc.msg} at column {exc.colno})")
            continue
        problems = validate_record(obj, where)
        if problems:
            errors.extend(problems)
            continue
        tid = obj["trace_id"]
        if tid in seen:
            errors.append(f"{where}: duplicate trace_id {tid!r} (first seen on line {seen[tid]})")
            continue
        seen[tid] = lineno
        traces.append(_to_trace(obj))
    return traces, errors


def validate_file(path: str | Path) -> tuple[list[Trace], list[str]]:
    """Validate a traces file without raising. Returns (traces, errors)."""
    p = Path(path)
    if not p.exists():
        return [], [f"{p}: file not found"]
    with p.open(encoding="utf-8") as fh:
        traces, errors = parse_lines(fh, str(p))
    if not traces and not errors:
        errors.append(f"{p}: no traces found (file is empty)")
    return traces, errors


def load_traces(path: str | Path) -> list[Trace]:
    """Load a traces file, raising :class:`TraceValidationError` on any problem."""
    traces, errors = validate_file(path)
    if errors:
        raise TraceValidationError(errors)
    return traces


def write_traces(traces: Iterable[Trace], path: str | Path) -> int:
    """Write traces as JSONL. Returns the number written."""
    n = 0
    with Path(path).open("w", encoding="utf-8") as fh:
        for t in traces:
            fh.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n
