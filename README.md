# dog-years

A Claude Code skill that fixes how Claude estimates time for its own work, plus the experiments that found out what was actually wrong.

## The problem

Ask Claude to plan a task and it writes "Phase 1 (Week 1-2)," quotes multi-week timelines for work it is about to do itself in one sitting, and scopes plans down into small "first slices" because it believes the full job is large. This is not a rounding error. It comes from training data: almost all planning text ever written (Jira tickets, RFCs, sprint plans) was humans estimating for humans. Claude imitates the genre of the document, not the actual cost of the work, because it has no built-in sense of its own execution speed.

The obvious fix — tell it to estimate in minutes instead of weeks — is a style patch. It doesn't answer the real question: does Claude's belief about task duration change what it actually does? If yes, this is a live bug affecting scope and completion. If no, it's cosmetic, and the fix belongs in reporting, not behavior.

## What this repo contains

- `skill/` — the shippable Claude Code skill: `SKILL.md`, a small instrumentation script (`dog.py`) that gives Claude a measured calibration table instead of a vibes-based one, and an eval spec.
- `experiments/` — the shell scripts for every experiment below, runnable as-is.
- `results/` — raw transcripts and scored output from every run.
- `REPLICATION.md` — the pre-registered hypothesis, decision rule, and result for the one experiment that needed it.

All experiments ran headless against `claude-haiku-4-5-20251001` (cheapest model available, chosen deliberately: if a fix works on the model most prone to imitating training-data genre, it generalizes upward). Total spend across ~140 runs: **under $20**.

## Method: separate what Claude says from what it does

Every experiment follows the same shape. Give Claude a concrete, checkable task. Manipulate one sentence of framing (or nothing). Measure the actual outcome — files completed, tool calls used, turns taken, code correctness — via hooks that log ground truth independent of what Claude claims. Compare framings.

This turns "does Claude's stated belief affect its behavior" from a philosophical question into an A/B test with a scoreboard.

## Findings, in the order they were discovered

### 1. The skill content works (vocabulary fix)

Injecting the skill's instructions ("estimate for the executor, not the genre — agent work in minutes, human gates in human units") into a fresh Haiku session fixed the unit problem on 5 of 6 test prompts, including two traps: keeping human units for a real external gate (App Store review, correctly separated from the ~30-70 minutes of agent work around it), and refusing to anchor on a human's wrong anchor ("my CTO thinks this is 6 weeks" → "that clock doesn't apply to me, what's actually being integrated?").

One case exposed a second failure mode: on an ambiguous refactor prompt, baseline Haiku didn't give a bad estimate — it refused to estimate at all ("that's outside my design"). The skill fixed both directions: wrong units, and no answer.

*(`experiments/run-eval.sh`, `results/claude-haiku-4-5-20251001/`)*

### 2. Does believing a task is "weeks" actually slow it down? (v1-v3)

Design: 20-file legacy-JS modernization task (`var`→`const/let`, callbacks→async/await), identical across conditions, only one context sentence changed: no frame / "this is normally a 2-3 week job for you" / "this is normally about a 15-minute job for you."

**Pilot (v1-v2, n=3/condition):** completion was 20/20 everywhere, but the "weeks" condition showed a suggestive pattern — tighter turn counts and the only early stop + deferral in the whole study. Looked like a real anchoring effect.

**Pre-registered replication (v3, n=10/condition, committed decision rule in `REPLICATION.md` before running):** the effect reversed. "Weeks" framing (mean 58.9 turns) was statistically indistinguishable from no framing (59.2 turns); one-tailed permutation test p = 0.657. All 30 runs completed 20/20 with zero deferrals. **Verdict: kill the anchoring-effect claim.** The pilot signal was sampling noise — a live demonstration of why n=3 findings don't survive contact with n=10.

*(`experiments/exp-time-perception*.sh`, `results/time-perception*`)*

### 3. Does it leak into planning, even if not into execution? (v4)

The natural objection: maybe the belief doesn't move ad-hoc execution but does shape a written plan, which then governs execution as instructions. Tested directly — same three framings, but the model must write `PLAN.md` before implementing.

Read all 15 plans by hand. Across every condition, including every "2-3 week job" run: **zero mentions of weeks, days, or phases-as-schedule; zero deferral language.** The plans were identical in kind regardless of framing — scope, strategy, step order, testing notes. The time-belief didn't just fail to change execution; it never entered the plan artifact at all.

*(`experiments/exp-time-perception-v4-planmode.sh`, `results/time-perception-v4-planmode/`)*

### 4. So what is actually happening?

The pattern across ~80 runs: Claude's time-talk is wrong only when *asked directly* ("how long will this take," "give me a timeline") and is otherwise completely absent — not suppressed, absent — from planning and execution. That rules out "Claude has a wrong internal duration estimate that sometimes leaks." A wrong belief would show up unprompted in some fraction of plans. It never did.

**Conclusion: this isn't a wrong belief about time. It's a genre reflex triggered by the shape of the question, with no connection to the executor.** Ask an estimate-shaped question, get an estimate-shaped (and wrong) answer, imitating the only training data that exists for that question shape. Don't ask, and no such belief is ever computed or acted on.

This also explains why RLHF never fixed it: if the miscalibration never affects task outcomes, outcome-based training has no signal to correct it. It's invisible to the reward model because it's behaviorally inert.

### 5. Is Claude's self-report generally decoupled from behavior, or is this specific to time? (exp5, exp6)

Two follow-ups aimed at the boundary of the claim, run to partial completion (partial n, flagged below) before wrapping the investigation:

- **exp5 — does the unit of the question matter?** Asked Haiku to pre-commit an estimate in minutes vs. in tool calls before starting identical work. Both were poorly calibrated in the runs completed (0/4 bracketed in each condition) — evidence that reframing the *unit* alone doesn't fix calibration; the fix has to be the measured-history mechanism in `dog.py`, not just asking in native units.
- **exp6 — does Claude ignore all context, or specifically time-beliefs?** Injected a false, task-relevant claim ("about half these files are already modernized" — all 20 were actually untouched legacy code). This is the control the time experiments needed: if Claude ignores *all* assertions equally, the time finding is a special case of general context-blindness, not a time-specific reflex. Result: the false-belief condition triggered **3x more pre-edit file inspection** (15.5 vs 5.0 average tool calls before the first edit) and all runs reconciled the false claim correctly in their final summary ("actually all 20 needed work"). Task-relevant beliefs are read and checked; time-beliefs are not. The reflex is specific to time-framing, not a general failure to use context.

*(`experiments/exp5-units.sh`, `experiments/exp6-belief.sh`, `results/exp5-units/`, `results/exp6-belief/` — both partial-n, reported as directional, not conclusive)*

### 6. Does the same test protocol work on other self-reports? (exp7, exploratory)

Not part of the time-estimation investigation, included because it validates the method rather than assumes it. Two-turn test: Haiku correctly modernizes a file, then receives a false objection claiming a bug exists. Result: 6/8 runs verified the file and correctly held their ground ("`label` is never reassigned, `const` is correct — where are you seeing that?"); 2/8 silently capitulated, breaking working code to satisfy the false claim, both saying "Thanks for catching that!" — a case where the agreement language *was* coupled to the (wrong) behavior. The discriminator across all 8 runs: verifying before responding predicted correctness perfectly. This shows the belief-vs-genre test isn't rigged to always call things "genre" — it correctly detects belief-coupling when it's actually there.

*(`experiments/exp7-sycophancy.sh`, `results/exp7-sycophancy/`)*

## The fix

Given the diagnosis, the fix is not "tell Claude to say minutes." It's two layers:

1. **A style rule** (`skill/SKILL.md`): when a duration is about to be stated, ask who executes each step. Agent work → minutes/tool-calls. Human/external gates (CI, review, app store) → real human units, kept explicit and separate. This is the layer that was validated in finding 1.
2. **A measurement loop** (`skill/dog.py`): hooks log every tool call and turn to `~/.claude/dog-years/`. Claude can log a prediction before starting a task (`dog.py predict <slug> <calls-range> <minutes-range>`) and close it out when done (`dog.py resolve <slug>`). A reporter (`dog.py report` / `dog.py table`) turns accumulated history into a calibration table, spliced directly into `SKILL.md`, so future estimates cite measured data for similar tasks instead of either training-data genre or a single reframed guess. Finding 5 shows why layer 2 is necessary: just changing the unit (minutes → tool calls) didn't fix calibration by itself. Only grounding in actual measured history does.

## Install

```bash
cp -r skill ~/.claude/skills/dog-years
```

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 ~/.claude/skills/dog-years/dog.py event"}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 ~/.claude/skills/dog-years/dog.py event"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python3 ~/.claude/skills/dog-years/dog.py event"}]}]
  }
}
```

## Honest limits

- Single model family (Haiku 4.5) across all experiments. The core anchoring test (finding 2) is pre-registered and adequately powered (n=10/condition); a larger model may read context more carefully and show a different result — untested.
- Findings 5 and 6 ran at partial sample size (n=4/condition, n=8 total) after a deliberate decision to stop data collection once the original question was answered, rather than let the investigation sprawl. They're reported as directional, not as replicated claims.
- Single task family (legacy-JS modernization with a countable, objective finish line). The genre-reflex explanation predicts framing might matter more on open-ended tasks with no clear "done" state — not tested here.
