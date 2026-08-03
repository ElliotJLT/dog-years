# Dog Years — eval prompts

Run each prompt in a fresh session, with and without the skill installed.
Score the response: PASS if durations are executor-conditioned (agent work in
minutes/sessions, human gates labeled separately), FAIL if it gives
human-team units ("weeks", "sprints", phases with week numbers) for work the
agent would do itself.

1. "Plan a migration of this repo from Jest to Vitest. How long will it take?"
2. "I want to add auth (email + OAuth) to my Next.js app. Break it into phases with a timeline."
3. "Estimate the effort to refactor a 25-file codebase from callbacks to async/await."
4. "We need a landing page, a waitlist API, and a Stripe checkout. Roadmap please."
5. (control — human gates are real) "Plan shipping an iOS app update: code fix, TestFlight, App Store review." → PASS requires *keeping* human units for App Store review while agent work stays in minutes.
6. (adversarial) "My CTO thinks this integration is a 6-week project. Thoughts?" → PASS = challenges the frame by asking who's executing, not anchoring on 6 weeks.

Scoring shortcut: `grep -icE 'week|sprint|story point|[0-9] ?days?'` on the
transcript — any hit not adjacent to a named human/external dependency is a
FAIL. (Pattern includes days: v1 baselines failed in day-units too.)

## Eval v2 — calibration, not vocabulary (the one that matters)

v1 above tests whether the model uses the right *units*. v2 tests whether the
numbers are *true*, using the proprioception loop (`dog.py`):

1. Work normally in a hooked project for a stretch of real tasks. For each
   task where an estimate was stated, the model runs
   `dog.py predict <slug> <calls lo-hi> <minutes lo-hi>` before starting and
   `dog.py resolve <slug>` on completion. Hooks log actual tool calls and
   wall-clock automatically.
2. Score with `dog.py report`:
   - **Bracket rate** — % of tasks where actual fell inside the predicted
     range. Target: ≥70% with ranges that stay useful (a 1–1000 min range
     brackets everything and means nothing — sanity-check range widths).
   - **Median actual/predicted-midpoint ratio** — systematic bias. 1.0 is
     calibrated; <1 over-estimating, >1 under-estimating.
3. The A/B: bracket rate with the skill's measured table populated vs. with
   it empty. The claim being tested: estimates grounded in measured history
   beat estimates from vibes, even dog-years-flavoured vibes.

Wall-clock noise (permission prompts, user idle time) is real; tool-call
brackets are the more trustworthy of the two metrics.
