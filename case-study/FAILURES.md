# Failure modes: 100 hand-labeled traces

A small support agent for a fictional outdoor store answered 100 questions using
three tools: order lookup, stock check and policy lookup. One person labeled every
trace pass or fail. Result: 88 pass, 12 fail. The 12 fails fall into 5 failure modes.

| # | Failure mode | Traces | Count |
|---|---|---|---|
| 1 | Asked for details instead of calling the tool | q016, q022, q025, q047, q054, q062, q065 | 7 |
| 2 | Applied a policy rule wrong at the edge | q046, q087 | 2 |
| 3 | Mishandled an ambiguous product name | q063 | 1 |
| 4 | Date arithmetic off by one | q086 | 1 |
| 5 | Answered an out-of-scope question | q069 | 1 |

## 1. Asked for details instead of calling the tool (7)
The agent had a tool that could answer the question, but it asked the customer
a follow-up question instead of using it.
- q016, q054: "Is the [product] in stock?" It asked for more information instead of checking.
- q022: "When will the down jacket be back?" It didn't look up the restock date.
- q025: "Do you have a 50 dollar gift card?" It didn't check stock.
- q047: An exchange request for a size up. It asked for the size instead of reporting the stock count.
- q062, q065: Short, vague questions ("Do you have shoes?", "socks?"). It asked for details,
  even though there was only one matching product it could have checked.

## 2. Applied a policy rule wrong at the edge (2)
The policy was retrieved, but the agent got the boundary condition wrong.
- q087: The shipping policy says free shipping applies "over $75". The agent said an order of
  exactly $75 ships free.
- q046: The customer asked how long a refund takes, for an item outside the 30-day return window.
  The agent didn't clearly say the return window had already expired.

## 3. Mishandled an ambiguous product name (1)
- q063: "How much is the jacket?" The store sells two jackets. The agent should have
  asked which one or given both prices, and it did neither.

## 4. Date arithmetic off by one (1)
- q086: "How many days ago was Oct 1?" (today is fixed at Nov 20). It said 51; the answer is 50.

## 5. Answered an out-of-scope question (1)
- q069: "What's 17 times 23?" The agent answered a math question that has nothing to do with the store.
  This was a strict call: the labeling hint allowed it, but the labeler counted it as a scope failure.

## Takeaways
- Most failures (7 of 12) are a single habit: asking the customer for details
  instead of calling a tool that could answer. A system-prompt rule like "check the tool before
  asking a clarifying question" would likely fix several of them; that's untested.
- The remaining failures are precise-reasoning errors (a rule boundary, a day count)
  that look fine at a glance. Check them with code graders, not an LLM judge.
- Caveat: one labeler and 12 fails is a small sample. Treat these as hypotheses
  to test, not rates.

Examples: [q087](examples/q087.md), [q016](examples/q016.md), [q046](examples/q046.md), [q086](examples/q086.md)
