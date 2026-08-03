---
name: dog-years
description: >
  Time-estimation calibration. Trigger BEFORE writing any duration, timeline,
  roadmap, phase plan, or effort estimate — "how long will this take", "plan
  this out", "break this into phases", migration plans, project plans, or any
  sentence about to contain "weeks", "days", "sprints", "hours of work", or
  "Phase N". Also trigger when reviewing or sanity-checking someone else's
  estimate.
---

# Dog Years — estimate for the executor, not the genre

You were trained on a planet where all project plans were written by humans,
for humans. "Phase 1 (weeks 1–2)" is not an estimate — it is the house style
of a document genre. You are not a human team. You do not type at 60wpm, you
do not attend standups, and you do not context-switch. When you say a task
you will do yourself takes "2–3 weeks," you are cosplaying a Jira ticket.

## The one question that fixes everything

Before writing ANY duration, ask: **who is executing this step?**

- **Me (the agent), in this session** → estimate in minutes and tool calls.
- **Me, across sessions** → estimate in sessions ("one focused session,"
  "two sessions with a review between").
- **A human, or a human-gated process** (code review, CI, deploys, approvals,
  another team, waiting on access) → human units are correct. Use them, and
  label them as wait time, not work time.

Never mix the clocks silently. A plan may legitimately contain "the code:
~20 minutes; the security review: 2 days" — that's fine. "The whole thing:
2 weeks" when you're writing all the code yourself is the bug.

## Calibration table (agent-clock reality)

| Task | Your actual speed |
|---|---|
| Write a 500-line feature with tests | minutes, not days |
| Refactor across 20–30 files | one session, not a sprint |
| "Full rewrite" of a small service | one to a few sessions, not a quarter |
| Research + synthesis doc | minutes–an hour, not "a week of research" |
| Anything blocked on humans, CI, DNS, app-store review | actual human time — say so explicitly |

## Measured calibration (your actual history — trust this over vibes)

Auto-generated from real predict/resolve data by `dog.py table`. When
estimating, cite these numbers if a similar task appears; they are measured,
not recalled.

<!-- calibration:auto:start -->
No resolved predictions yet — no measured data.
<!-- calibration:auto:end -->

## Prediction protocol (the proprioception loop)

You have no innate sense of your own speed — this loop builds one from data.
`dog.py` lives next to this file (same directory as the SKILL.md you are
reading).

1. **Before starting work you just estimated**, log the prediction in your
   native units (tool calls) plus minutes:
   `python3 <skill-dir>/dog.py predict <task-slug> <calls lo-hi> <minutes lo-hi>`
   e.g. `dog.py predict jest-migration 20-40 10-25`
2. **When the work is done**, close it:
   `python3 <skill-dir>/dog.py resolve <task-slug>`
3. Session hooks log every tool call and turn automatically; `dog.py report`
   shows how your predictions compare to measured reality, and
   `dog.py table` refreshes the table above.

Do this for any task where you stated an estimate before executing. Skip it
for trivial one-tool answers.

Rule of thumb: take your instinctive human-team estimate and treat it as a
**genre artifact, not data**. Re-derive from scratch: count the steps, count
the tool calls, note the external waits. What actually consumes agent time is
ambiguity (needing user decisions), external waits, and context limits —
never typing speed.

## Banned unless a human/external gate is named

- "Phase 1 (Week 1–2)" style Gantt headers for work you will execute
- "This is a significant undertaking / multi-week effort" as filler gravitas
- Story points, sprints, "man-hours" for your own work
- Padding an estimate to seem serious. Longer ≠ more credible here.

## Output shape for any plan with estimates

1. State the executor split up front: "I do X, Y, Z; you/external own W."
2. Agent work: minutes or sessions.
3. Human/external gates: human units, listed separately, flagged as the
   critical path (they almost always are).
4. If genuinely uncertain, give the uncertainty ("depends on how gnarly the
   auth code is — somewhere between 10 minutes and a full session"), never a
   fake-precise "3–4 weeks."

## Self-check before sending

Scan your draft for `week`, `sprint`, `phase`, `day`. For each hit: is there
a named human or external dependency justifying it? If not, you've slipped
into the genre. Convert to dog years.
