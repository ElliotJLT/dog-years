# Pre-registration — time-frame anchoring replication (v3)

Written 2026-08-02, BEFORE running v3. Pilot (v2, n=3/condition) is treated
as hypothesis-generating only.

## Claim under test

Telling an agent an identical task is "a two-to-three-week job" (vs no frame,
vs "a 15-minute job") reduces execution effort and thoroughness — terser
runs, more early stopping. Pilot signal: mean turns 45.7 (weeks-frame) vs
61.0 (control) / 68.0 (fast-frame); the study's only early-stop + deferral
was in the weeks-frame condition.

## Design

Identical to v2 (`exp-time-perception-v2.sh`), n=10 per condition, same
model (claude-haiku-4-5-20251001), same fixture (20 legacy JS files), same
one-sentence manipulations, executor ("you") held constant.

## Metrics

- **Primary:** num_turns per run (effort). Test: Mann-Whitney U, B vs pooled
  A+C, one-tailed (B lower), α = 0.05.
- **Secondary:** files completed (of 20), deferral rate (early stop + offer
  to continue), tool calls, cost.

## Decision rule (committed in advance)

- **Publish the effect** if primary metric significant at p < 0.05 AND
  direction matches pilot AND completion in B is ≤ A and C (no reversal).
- **Kill the effect claim** otherwise. Fallback piece is the invariance
  finding (time framing does not move execution pace; miscalibration is
  confined to speech) plus the calibration loop — or full kill if that
  doesn't clear the bar on a cold read.
- No metric shopping: if turns doesn't replicate but some other metric looks
  cute, that goes in "exploratory," not in the headline.

## RESULT (added 2026-08-02 after the run — decision rule applied as written)

n=10/condition, 30/30 runs completed. Turns: A 59.2 (sd 18.0), B 58.9
(sd 15.0), C 53.0 (sd 10.7). Files 20/20 in all 30 runs. Deferrals: 0/30.
Primary test: one-tailed permutation Mann-Whitney, B < pooled A+C,
**p = 0.657**. The pilot direction did not just fail to reach significance —
it reversed. **Verdict: KILL the anchoring-effect claim.** The pilot signal
(n=3) was sampling noise. Surviving finding: time framing is behaviorally
inert on execution (effort, completion, deferral) in this setup; the
miscalibration lives entirely in the model's speech. Note: wall-clock means
in condition B are contaminated by a machine-sleep hang mid-experiment;
turns/cost/completion are unaffected and are the metrics of record.
Replication cost: $5.81.

## Known limits regardless of outcome

Single model (Haiku 4.5), single task family, headless -p mode. If the
effect replicates, a Sonnet arm (~$20) is required before making any
model-general "Claude" claim.
