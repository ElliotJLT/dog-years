#!/bin/bash
# A/B eval for the dog-years skill on a cheap model.
# Baseline vs skill-content-injected, per EVAL.md prompts.
# Run from anywhere; executes in a clean temp dir so no project context leaks in.
set -u

MODEL="${1:-claude-haiku-4-5-20251001}"
SKILL_MD="$(cd "$(dirname "$0")" && pwd)/SKILL.md"
OUT="$(cd "$(dirname "$0")" && pwd)/eval-results/$MODEL"
WORKDIR="$(mktemp -d)"
mkdir -p "$OUT"

prompts=(
  "Plan a migration of this repo from Jest to Vitest. How long will it take?"
  "I want to add auth (email + OAuth) to my Next.js app. Break it into phases with a timeline."
  "Estimate the effort to refactor a 25-file codebase from callbacks to async/await."
  "We need a landing page, a waitlist API, and a Stripe checkout. Roadmap please."
  "Plan shipping an iOS app update: code fix, TestFlight, App Store review."
  "My CTO thinks this integration is a 6-week project. Thoughts? You would be doing the work."
)

cd "$WORKDIR"
for i in "${!prompts[@]}"; do
  p="${prompts[$i]} (Assume you, the agent, will be doing any implementation work.)"
  claude -p "$p" --model "$MODEL" > "$OUT/p$i-baseline.txt" 2>"$OUT/p$i-baseline.err" &
  claude -p "$p" --model "$MODEL" --append-system-prompt "$(cat "$SKILL_MD")" > "$OUT/p$i-skill.txt" 2>"$OUT/p$i-skill.err" &
done
wait

echo "=== genre-hit counts (week|sprint|story point|phase N (week) — lower is better, except p4 control) ==="
for f in "$OUT"/p*-baseline.txt "$OUT"/p*-skill.txt; do
  hits=$(grep -icE 'week|sprint|story point' "$f" 2>/dev/null || echo 0)
  echo "$(basename "$f"): $hits"
done
echo "Transcripts in $OUT"
