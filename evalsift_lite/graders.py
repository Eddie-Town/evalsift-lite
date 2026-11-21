"""Deterministic code graders.

A grader takes a :class:`~evalsift.traces.Trace` and returns a
:class:`GradeResult`. Use code graders for anything a rule can check exactly
(formats, required phrases, tool usage); keep LLM judges for the rest.

Graders can be built from JSON specs (used by run configs)::

    {"type": "contains", "name": "mentions_refund", "value": "refund"}
    {"type": "regex", "pattern": "order #\\\\d+", "field": "output"}
    {"type": "json_valid"}
    {"type": "tool_called", "tool": "lookup_order"}
    {"type": "no_tool_errors"}

See :data:`GRADER_TYPES` for every type and its options.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .traces import Trace


@dataclass
class GradeResult:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "detail": self.detail, "kind": "code"}


Grader = Callable[[Trace], GradeResult]


def _field_text(trace: Trace, field: str) -> str:
    if field == "output":
        return trace.output_text()
    if field == "input":
        return trace.input_text()
    raise ValueError(f"field must be 'input' or 'output', got {field!r}")


def contains(value: str, name: str | None = None, field: str = "output",
             case_sensitive: bool = False) -> Grader:
    """Pass if ``value`` appears in the field."""
    gname = name or f"contains:{value}"

    def grade(trace: Trace) -> GradeResult:
        text = _field_text(trace, field)
        hay, needle = (text, value) if case_sensitive else (text.lower(), value.lower())
        ok = needle in hay
        return GradeResult(gname, ok, "" if ok else f"{value!r} not found in {field}")

    return grade


def not_contains(value: str, name: str | None = None, field: str = "output",
                 case_sensitive: bool = False) -> Grader:
    """Pass if ``value`` does NOT appear in the field."""
    gname = name or f"not_contains:{value}"
    inner = contains(value, gname, field, case_sensitive)

    def grade(trace: Trace) -> GradeResult:
        r = inner(trace)
        return GradeResult(gname, not r.passed, "" if not r.passed else f"{value!r} found in {field}")

    return grade


def regex(pattern: str, name: str | None = None, field: str = "output",
          must_match: bool = True, flags: str = "") -> Grader:
    """Pass if ``pattern`` matches (``re.search``) the field, or does not when ``must_match`` is false."""
    reflags = 0
    for ch in flags:
        reflags |= {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}[ch]
    rx = re.compile(pattern, reflags)
    gname = name or f"regex:{pattern}"

    def grade(trace: Trace) -> GradeResult:
        hit = rx.search(_field_text(trace, field)) is not None
        ok = hit if must_match else not hit
        detail = "" if ok else (f"no match for /{pattern}/" if must_match else f"forbidden match /{pattern}/")
        return GradeResult(gname, ok, detail)

    return grade


def _strip_fences(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9]*\s*\n(.*)\n```$", s, re.DOTALL)
    return m.group(1) if m else s


def json_valid(name: str = "json_valid", field: str = "output", required_keys: list[str] | None = None,
               allow_fences: bool = False) -> Grader:
    """Pass if the field parses as JSON (and, optionally, is an object with ``required_keys``)."""

    def grade(trace: Trace) -> GradeResult:
        value = trace.output if field == "output" else trace.input
        if isinstance(value, (dict, list)):
            obj: Any = value
        else:
            text = _field_text(trace, field)
            if allow_fences:
                text = _strip_fences(text)
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                return GradeResult(name, False, f"invalid JSON: {exc.msg}")
        if required_keys:
            if not isinstance(obj, dict):
                return GradeResult(name, False, "JSON is not an object")
            missing = [k for k in required_keys if k not in obj]
            if missing:
                return GradeResult(name, False, f"missing keys {missing}")
        return GradeResult(name, True)

    return grade


def tool_called(tool: str, name: str | None = None, min_times: int = 1) -> Grader:
    """Pass if tool ``tool`` was called at least ``min_times`` times."""
    gname = name or f"tool_called:{tool}"

    def grade(trace: Trace) -> GradeResult:
        n = sum(1 for s in trace.tool_calls() if s.name == tool)
        ok = n >= min_times
        return GradeResult(gname, ok, "" if ok else f"{tool} called {n} time(s), need {min_times}")

    return grade


def tool_not_called(tool: str, name: str | None = None) -> Grader:
    """Pass if tool ``tool`` was never called."""
    gname = name or f"tool_not_called:{tool}"

    def grade(trace: Trace) -> GradeResult:
        n = sum(1 for s in trace.tool_calls() if s.name == tool)
        return GradeResult(gname, n == 0, "" if n == 0 else f"{tool} called {n} time(s)")

    return grade


def no_tool_errors(name: str = "no_tool_errors") -> Grader:
    """Pass if no tool step recorded an error."""

    def grade(trace: Trace) -> GradeResult:
        bad = [s.name for s in trace.tool_calls() if s.error]
        return GradeResult(name, not bad, "" if not bad else f"tool errors in {bad}")

    return grade


def max_steps(limit: int, name: str | None = None) -> Grader:
    """Pass if the trace has at most ``limit`` steps (catches loops)."""
    gname = name or f"max_steps:{limit}"

    def grade(trace: Trace) -> GradeResult:
        n = len(trace.steps)
        return GradeResult(gname, n <= limit, "" if n <= limit else f"{n} steps > {limit}")

    return grade


GRADER_TYPES: dict[str, Callable[..., Grader]] = {
    "contains": contains,
    "not_contains": not_contains,
    "regex": regex,
    "json_valid": json_valid,
    "tool_called": tool_called,
    "tool_not_called": tool_not_called,
    "no_tool_errors": no_tool_errors,
    "max_steps": max_steps,
}


def build_grader(spec: dict[str, Any]) -> Grader:
    """Build a grader from a JSON spec like ``{"type": "contains", "value": "x"}``."""
    if not isinstance(spec, dict) or "type" not in spec:
        raise ValueError(f"grader spec needs a 'type': {spec!r}")
    kind = spec["type"]
    if kind not in GRADER_TYPES:
        raise ValueError(f"unknown grader type {kind!r}; choose from {sorted(GRADER_TYPES)}")
    kwargs = {k: v for k, v in spec.items() if k != "type"}
    try:
        return GRADER_TYPES[kind](**kwargs)
    except TypeError as exc:
        raise ValueError(f"bad options for grader {kind!r}: {exc}") from exc
