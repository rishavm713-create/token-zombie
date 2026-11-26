---
name: tz-ambition
description: Make a big or goal-driven task more ambitious before building it: ask for the outcome (altitude), the expert method (depth), and the fields that bear on it (range), then check the agent has what it needs. Use when a task is large, open-ended or "build X" with an outcome behind it; skip for small fixes.
license: MIT
---

# ambition

Idea source: Felix Rieseberg, "How to be more ambitious" (2026-10-13). Own wording, not a copy.
Use only for large or goal-driven work. For a small fix, just do it.

## 1. Altitude: outcome, not task
State the goal behind the task in one line ("so that hiring gets faster"), then ask for: what changed, why, and the 2-3 decisions to make now with the case for and against each. Where a process repeats, ask whether the process itself should change. Fits goal-driven work, not creative work.

## 2. Depth: the expert version, not the bigger one
Before rewriting the task, answer in 4 short lines:
1. What would a top professional do that was not asked for?
2. What is the rawest material they would start from?
3. Which methods and tools do they use (not markdown tables when a database or statistical model is the real method)?
4. What outside the model verifies the result (test, tool, data, a second model such as Codex), never self-grading?
Then rewrite the task to ask for exactly that. Set a hard target and say it is reasonable (e.g. 200 ms, not 5 s). Test the team's belief against raw data ("try to reproduce that claim from the data").

## 3. Range: borrow from other fields
Turn the noun into a verb ("a quarterly review" -> "make busy people believe a cause-and-effect story and decide under uncertainty in 30 minutes"). Name 3-5 fields that bear on it, plus one adversary (red team). Each role does that field's work; no role-play or tone changes. Run roles one after another, each fixing what it finds before the next starts; use subagents only if the task is large enough to repay their cost.

## 4. Resources (check before starting)
- Can the agent see the problem (raw data, logs, a reproduction)?
- Does it have the context about the app?
- Is there a safe place to test its own fixes, and can it install what it needs?
If any answer is no, fix that first or say what is missing.

## Output
End with one line: which of the 4 steps changed the plan, and what is still unverified.
