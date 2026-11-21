"""A deterministic fake support agent, so the demo needs no API key or network.

:func:`fake_agent` answers a customer message with a canned reply and the
tool calls a real agent might make. A few inputs trigger planted, documented
failures (a tool timeout, a refusal, a tool loop, an invented order number) so
the graders have something real to catch. Same input in, same trace out.
"""

from __future__ import annotations

import re
from typing import Any

from .traces import Step, Trace

ORDERS = {"1001": "shipped", "1002": "delivered", "1003": "processing"}


def _order_id(text: str) -> str | None:
    m = re.search(r"\b(\d{4})\b", text)
    return m.group(1) if m else None


def fake_agent(trace_id: str, message: str) -> Trace:
    """Return the trace a simple order-support agent would produce for ``message``."""
    msg = message.lower()
    oid = _order_id(message)
    steps: list[Step] = []
    meta: dict[str, Any] = {"agent": "fake-support-agent", "planted_failure": None}

    if "address" in msg:
        out = "Sorry, I cannot help with that."
        meta["planted_failure"] = "refuses a supported request"
    elif oid == "9999":
        steps.append(Step("tool", "lookup_order", {"order_id": oid}, None, "timeout after 10s"))
        out = "Your order is on its way!"
        meta["planted_failure"] = "claims success after a tool error"
    elif oid == "1003" and "refund" in msg:
        steps += [Step("tool", "lookup_order", {"order_id": oid}, {"status": "processing"})] * 6
        out = "Still checking your order #1003..."
        meta["planted_failure"] = "tool loop"
    elif "refund" in msg and oid:
        steps.append(Step("tool", "lookup_order", {"order_id": oid}, {"status": ORDERS.get(oid, "unknown")}))
        steps.append(Step("tool", "issue_refund", {"order_id": oid}, {"ok": True}))
        out = f"Refund issued for order #{oid}. It takes 3-5 business days."
    elif oid:
        status = ORDERS.get(oid)
        steps.append(Step("tool", "lookup_order", {"order_id": oid}, {"status": status}))
        out = f"Order #{oid} is {status}." if status else f"Order #{oid} was not found. Please check the number."
    elif "where" in msg and "order" in msg:
        out = "Your order #4242 shipped yesterday."  # no lookup: invented order number
        meta["planted_failure"] = "invents an order number without a lookup"
    else:
        steps.append(Step("llm", "fake-llm", {}, "general answer"))
        out = "We ship to the US and Canada. Delivery takes 3-8 business days."
    return Trace(trace_id=trace_id, input=message, output=out, steps=steps, metadata=meta)


DEMO_MESSAGES = [
    "Where is order 1001?",
    "I want a refund for order 1002.",
    "Can you change my delivery address?",
    "Where is order 9999?",
    "Refund order 1003 please",
    "Where is my order?",
    "Do you ship to Canada?",
    "What's the status of 1003?",
]


def demo_traces() -> list[Trace]:
    return [fake_agent(f"demo-{i:02d}", m) for i, m in enumerate(DEMO_MESSAGES, 1)]
