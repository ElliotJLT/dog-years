<p align="center">
  <img src="assets/dog-years.png" width="220" alt="A brown dog giving your project timeline a sceptical look">
</p>

<h1 align="center">dog-years</h1>

<p align="center">
  <em>Your agent is estimating in human years.</em>
</p>

<p align="center">
  A Claude Code skill for estimates that separate agent work from human waiting.
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#before--after">Before / after</a> ·
  <a href="docs/research.md">The experiments</a>
</p>

---

You ask your coding agent for a plan. It comes back with “Phase 1: Weeks 1–2.”

You're both sitting there. It can start now.

dog-years makes it ask **who is doing the work** before attaching a calendar to it. The agent gets its own estimate. Reviews, access requests and release queues get theirs.

## Before / after

Same prompt: *“Plan shipping an iOS app update: code fix, TestFlight, App Store review.”*

| Without dog-years | With dog-years |
|---|---|
| “Code Fix & Validation (Days 1-2)” | “Code fix & testing — 15–45 minutes” |
| “Total: ~14 days” | “Total agent time: ~30–70 minutes” |
| One combined timeline | Human and external waits listed separately |

Excerpts from the saved [baseline](results/claude-haiku-4-5-20251001/p4-baseline.txt) and [skill run](results/claude-haiku-4-5-20251001/p4-skill.txt), using Haiku 4.5. These are model estimates, **not measured completion times or current App Store guidance**. The demonstration shows the change in framing.

## Install

Copy this into Claude Code:

```text
Install the dog-years skill from https://github.com/ElliotJLT/dog-years.
Copy the contents of skill/ into ~/.claude/skills/dog-years/.
Keep my other skills and settings intact. Skip the optional measurement hooks.
```

Or use the skills CLI:

```sh
npx skills add ElliotJLT/dog-years --skill dog-years --agent claude-code --global
```

This installs the skill; measurement hooks are an optional separate step.

For a manual install:

```sh
git clone https://github.com/ElliotJLT/dog-years.git
cd dog-years
mkdir -p ~/.claude/skills/dog-years
cp -R skill/. ~/.claude/skills/dog-years/
```

Start a new Claude Code session and try:

```text
/dog-years Plan this migration. Separate your work from anything waiting on me.
```

The skill also asks Claude to apply it when writing timelines and estimates. Explicit invocation makes it easy to try on a particular task.

## The rule

Before stating a duration, identify the executor.

| Who does it? | What the estimate should describe |
|---|---|
| The agent | Its implementation and verification work, using comparable measurements where available |
| You or your team | Review, decisions, access and other human work |
| An external service | Builds, processing, release queues and other waits |

A smaller unit does not make an estimate more accurate. Missing context should remain visible as uncertainty.

## Give it a clock

The optional Python helper records predictions, elapsed time and tool-call counts. You can feed that history back into the skill before the next estimate.

```sh
python3 ~/.claude/skills/dog-years/dog.py report
```

An empty history says so. Set up the [measurement hooks](docs/measurement.md) to start collecting data. Elapsed time includes interruptions; the current implementation also has limits around overlapping sessions.

## What we tested

The original investigation includes a six-prompt framing check and a pre-registered, 30-run execution comparison on Haiku 4.5.

Telling the model a task would take “weeks” did **not** establish slower execution in that comparison. We dropped that claim. Improvements to prediction accuracy from measured history remain an open test.

Read the [methods, findings and limits](docs/research.md), inspect the [raw outputs](results/), or run the [experiments](experiments/).

## Contribute

Found an estimate that makes no sense? Open an issue with the prompt, model, output and whether dog-years was active. Remove private code and identifying details first. Include the observed duration if you measured it.

Built by [Elliot Little](https://www.elliotos.com/). More small workflow fixes in [Skill Potions](https://github.com/ElliotJLT/Claude-Skill-Potions).

[MIT](LICENSE).
