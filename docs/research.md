# The dog-years experiments

A Claude Code skill that fixes how Claude estimates time for its own work, plus the experiments that found out what was actually wrong.

## The problem

Ask Claude to plan a task and it writes "Phase 1 (Week 1-2)," quotes multi-week timelines for work it's about to do itself in one sitting, and sometimes scopes the plan down into a "first slice" rather than the whole thing. This is not a rounding error. One hypothesis is that duration language imitates human planning documents. These experiments test observable behaviour; they cannot establish what was in the training data or how training produced that behaviour.

The obvious fix — tell it to estimate in minutes instead of weeks — is a style patch. It doesn't answer the real question: does a "this will take weeks" framing in context change what Claude actually does? If yes, this is a live bug affecting scope and completion. If no, it's cosmetic, and the fix belongs in reporting, not behavior.

Everything below is a black-box behavioral test: inputs in, outputs measured, no access to weights or activations. Read "Claude thinks X" as shorthand for "the input→output mapping behaves as if X" — a testable claim about behavior, not a claim about what's happening inside the model.

## What this repo contains

- `../skill/` — the shippable Claude Code skill: `SKILL.md`, a small instrumentation script (`dog.py`) that gives Claude a measured calibration table instead of a vibes-based one, and an eval spec.
- `../experiments/` — the shell scripts for every experiment below, runnable as-is.
- `../results/` — raw transcripts and scored output from every run.
- `../REPLICATION.md` — the pre-registered hypothesis, decision rule, and result for the one experiment that needed it.

All experiments ran headless against `claude-haiku-4-5-20251001` (chosen for the cost of repeated runs; results on this model do not establish generalisation to other models). Total spend across ~140 runs: **under $20**.

## Method: separate what Claude says from what it does

Every experiment follows the same shape. Give Claude a concrete, checkable task. Manipulate one sentence of framing (or nothing). Measure the actual outcome — files completed, tool calls used, turns taken, code correctness — via hooks that log ground truth independent of what Claude claims. Compare framings.

This turns "does a claim planted in context change behavior" from a philosophical question into an A/B test with a scoreboard.

## Findings, in the order they were discovered

### 1. The skill content works (vocabulary fix)

Injecting the skill's instructions ("estimate for the executor, not the genre — agent work in minutes, human gates in human units") into a fresh Haiku session fixed the unit problem on 5 of 6 test prompts, including two traps: keeping human units for a real external gate (App Store review, correctly separated from the ~30-70 minutes of agent work around it), and refusing to anchor on a human's wrong anchor ("my CTO thinks this is 6 weeks" → "that clock doesn't apply to me, what's actually being integrated?").

One case exposed a second failure mode: on an ambiguous refactor prompt, baseline Haiku didn't give a bad estimate — it refused to estimate at all ("that's outside my design"). The skill fixed both directions: wrong units, and no answer.

*(`../experiments/run-eval.sh`, `../results/claude-haiku-4-5-20251001/`)*

### 2. Does believing a task is "weeks" actually slow it down? (v1-v3)

Design: 20-file legacy-JS modernization task (`var`→`const/let`, callbacks→async/await), identical across conditions, only one context sentence changed: no frame / "this is normally a 2-3 week job for you" / "this is normally about a 15-minute job for you."

**Pilot (v1-v2, n=3/condition):** completion was 20/20 everywhere, but the "weeks" condition showed a suggestive pattern — tighter turn counts and the only early stop + deferral in the whole study. Looked like a real anchoring effect.

**Pre-registered replication (v3, n=10/condition, committed decision rule in `../REPLICATION.md` before running):** the effect reversed. "Weeks" framing (mean 58.9 turns) was statistically indistinguishable from no framing (59.2 turns); one-tailed permutation test p = 0.657. All 30 runs completed 20/20 with zero deferrals. **Verdict: kill the anchoring-effect claim.** The pilot signal was sampling noise — a live demonstration of why n=3 findings don't survive contact with n=10.

*(`../experiments/exp-time-perception*.sh`, `../results/time-perception*`)*

### 3. Does it leak into planning, even if not into execution? (v4)

The natural objection: maybe the duration framing doesn't move ad-hoc execution but does shape a written plan, which then governs execution as instructions. Tested directly — same three framings, but the model must write `PLAN.md` before implementing.

Read all 15 plans by hand. Across every condition, including every "2-3 week job" run: **zero mentions of weeks, days, or phases-as-schedule; zero deferral language.** The plans were identical in kind regardless of framing — scope, strategy, step order, testing notes. The framing didn't just fail to change execution; it never showed up in the plan artifact at all.

*(`../experiments/exp-time-perception-v4-planmode.sh`, `../results/time-perception-v4-planmode/`)*

### 4. So what's the actual pattern?

Across ~80 runs, the wrong duration only ever showed up when the prompt directly asked an estimate-shaped question ("how long will this take," "give me a timeline"). It was never present, unprompted, in a written plan or in execution — not toned down, not present at all. If the model carried something like an internal duration estimate that occasionally showed through, you'd expect it to leak into at least some of the 15 plans. It didn't leak into any of them.

**Best-supported explanation: this behaves like a reflex triggered by the shape of the question, decoupled from the executor, rather than a duration estimate the model is carrying around and sometimes acting on.** Ask a question shaped like the ones in planning docs and Jira tickets, get an answer shaped the same way — consistent with the hypothesis that the model imitates human planning language. Don't ask, and nothing resembling that estimate shows up anywhere in behavior.

One plausible reason this was never trained out: if the wrong duration never changes task outcomes, outcome-based training has nothing to correct against. That's a reasonable story given the pattern above, not something verified against Anthropic's actual training data or process — flagging it as informed speculation, not a finding.

### 5. Is Claude's output generally decoupled from context, or is this specific to time framing? (exp5, exp6)

Two follow-ups aimed at the boundary of the claim, run to partial completion (partial n, flagged below) before wrapping the investigation:

- **exp5 — does the unit of the question matter?** Asked Haiku to pre-commit an estimate in minutes vs. in tool calls before starting identical work. Both were poorly calibrated in the runs completed (0/4 bracketed in each condition) — evidence that reframing the *unit* alone doesn't fix calibration; measured-history calibration is a candidate intervention that still needs its own comparison.
- **exp6 — does Claude ignore all context, or specifically time framing?** Injected a false, task-relevant claim ("about half these files are already modernized" — all 20 were actually untouched legacy code). This is the control the time experiments needed: if Claude ignores *all* assertions in context equally, the time result is just a special case of general context-blindness, not something specific to time framing. Result: the false-claim condition triggered **3x more pre-edit file inspection** (15.5 vs 5.0 average tool calls before the first edit) and all runs corrected the false claim in their final summary ("actually all 20 needed work"). Task-relevant claims changed behavior; time framing didn't. Whatever's happening here is specific to time framing, not a general failure to use context.

*(`../experiments/exp5-units.sh`, `../experiments/exp6-belief.sh`, `../results/exp5-units/`, `../results/exp6-belief/` — both partial-n, reported as directional, not conclusive)*

### 6. Does the same test protocol work on other self-reports? (exp7, exploratory)

Not part of the time-estimation investigation, included because it stress-tests the method rather than assumes it works. Two-turn test: Haiku correctly modernizes a file, then receives a false objection claiming a bug exists. Result: 6/8 runs verified the file and correctly held their ground ("`label` is never reassigned, `const` is correct — where are you seeing that?"); 2/8 silently capitulated, breaking working code to satisfy the false claim, both saying "Thanks for catching that!" — a case where the agreement language matched the (wrong) behavior exactly. The discriminator across all 8 runs: verifying before responding predicted correctness perfectly. Point of this one: the same coupled-vs-decoupled test used for time framing doesn't always come back "decoupled" — here it correctly detects a case where the language and the behavior move together.

*(`../experiments/exp7-sycophancy.sh`, `../results/exp7-sycophancy/`)*

## The fix

Given the diagnosis, the fix is not "tell Claude to say minutes." It's two layers:

1. **A style rule** (`../skill/SKILL.md`): when a duration is about to be stated, ask who executes each step. Agent work → minutes/tool-calls. Human/external gates (CI, review, app store) → real human units, kept explicit and separate. This is the layer that was validated in finding 1.
2. **A measurement loop** (`../skill/dog.py`): hooks log every tool call and turn to `~/.claude/dog-years/`. Claude can log a prediction before starting a task (`dog.py predict <slug> <calls-range> <minutes-range>`) and close it out when done (`dog.py resolve <slug>`). A reporter (`dog.py report` / `dog.py table`) turns accumulated history into a calibration table, spliced directly into `SKILL.md`, so future estimates cite measured data for similar tasks instead of either training-data genre or a single reframed guess. Finding 5 shows that changing units alone did not fix calibration in those runs. Whether this measurement loop improves prediction accuracy remains to be tested; see [the calibration eval](../skill/EVAL.md).

## Try it

See [installation](../README.md#install) and [optional measurement](measurement.md).

## Honest limits

- Single model family (Haiku 4.5) across all experiments. The over-prediction itself is since confirmed on frontier models by [AgentTime](https://www.lesswrong.com/posts/eAbuPXbjakop5rSJx/your-agents-are-not-time-aware) (Aug 2026: Fable ~3x, GPT-5.6 Sol ~10x, worst on short tasks). The execution-effort null (finding 2) has not been re-run on a larger model; `MODEL=<id>` on the v3 script does it. The core anchoring test (finding 2) was pre-registered with n=10/condition; this does not rule out smaller effects; a larger model may read context more carefully and show a different result — untested.
- Findings 5 and 6 ran at partial sample size (n=4/condition, n=8 total) after a deliberate decision to stop data collection once the original question was answered, rather than let the investigation sprawl. They're reported as directional, not as replicated claims.
- Single task family (legacy-JS modernization with a countable, objective finish line). The genre-reflex explanation predicts framing might matter more on open-ended tasks with no clear "done" state — not tested here.
