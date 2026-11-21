# EvalSift Lite

Find out how your LLM agent actually fails before you write a single eval.

EvalSift Lite is a free, MIT-licensed Python tool (3.10+, no dependencies, no API key) for
error analysis on LLM agent traces: it validates a `traces.jsonl` file, grades each trace with
deterministic code checks, and writes a Markdown/HTML report of what failed. It comes with a
case study: 100 traces from a tool-using support agent, labeled by hand.

## Try it (about a minute)
```bash
git clone <repo-url> && cd evalsift-lite
python -m venv .venv && . .venv/bin/activate
pip install -e .
python -m evalsift_lite.demo     # writes report.html, report.md, results.jsonl
```
The demo grades 8 traces from a fake support agent with 4 planted failures and catches all 4.

## What we found in 100 real traces
A support agent for a fictional outdoor store, with order, stock and policy tools.
One labeler, 88 pass and 12 fail. Full breakdown: [case-study/FAILURES.md](case-study/FAILURES.md)

| Failure mode | Fails |
|---|---|
| Asked for details instead of calling the tool | 7 |
| Applied a policy rule wrong at the edge ("over $75") | 2 |
| Mishandled an ambiguous product name | 1 |
| Date arithmetic off by one | 1 |
| Answered an out-of-scope question | 1 |

Examples worth reading:
- [q087: "free over $75" is not "free at $75"](case-study/examples/q087.md)
- [q016: asking instead of looking](case-study/examples/q016.md)
- [q046: a correct answer to the wrong question](case-study/examples/q046.md)
- [q086: off by one day](case-study/examples/q086.md)

The 100 questions are in [case-study/questions.jsonl](case-study/questions.jsonl), so you can run them
on your own agent and see whether it makes the same mistakes.

## Use it on your own traces
One JSON object per line: `trace_id`, `input`, `output`, optional `steps[]` (each with `type` set to
`llm` or `tool`, plus `name`, `args`, `result`, `error`) and optional `metadata{}`. Then:
```bash
python -m evalsift_lite.demo --traces your_traces.jsonl --out-dir out/
```
This runs the built-in checks; add your own in `evalsift_lite/graders.py`.

## What the paid kit adds
EvalSift adds agent skills for Claude Code, Codex and Cursor that walk you through error analysis,
building a failure taxonomy, writing an LLM judge, checking that judge against human labels,
and gating regressions in CI. It also includes the full case-study data: all 100 traces,
the labels with notes, and a note on how the labels were made.
<!-- checkout link -->

## License
MIT. See [LICENSE](LICENSE).
