#!/usr/bin/env python3
"""Score the committed result files.

The experiment scripts score a live run: they rely on .dir pointers into a
temp fixture tree that no longer exists once the run is over. That makes the
published numbers unverifiable from a clone. This script reads the committed
JSON directly and reports what can be checked without re-running anything:
turns, wall time and cost per condition.

Usage:  python3 experiments/score-saved.py results/time-perception-v3
"""
import json
import os
import re
import statistics
import sys
from collections import defaultdict


def load_first_object(path):
    """Read one result file.

    Returns (obj, note). Some saved files have trailing bytes from an
    interrupted write; a few are empty, from runs that produced no output at
    all. Empty runs are kept in the repo rather than deleted, and excluded
    from the aggregates rather than counted as zeros.
    """
    raw = open(path).read()
    if not raw.strip():
        return None, "empty"
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        try:
            obj, end = json.JSONDecoder().raw_decode(raw)
            return obj, "trailing" if len(raw) - end > 0 else None
        except json.JSONDecodeError:
            return None, "unparseable"


def main(outdir):
    runs = sorted(
        f for f in os.listdir(outdir)
        if f.endswith(".json") and re.match(r"^[A-Za-z]+\d+\.json$", f)
    )
    if not runs:
        sys.exit("no run files found in %s" % outdir)

    agg = defaultdict(list)
    trailing, skipped = [], []
    print("%-6s %6s %8s %8s" % ("run", "turns", "mins", "cost$"))
    for fname in runs:
        run = fname[:-len(".json")]
        cond = re.match(r"^([A-Za-z]+)", run).group(1)
        j, note = load_first_object(os.path.join(outdir, fname))
        if j is None:
            skipped.append("%s (%s)" % (fname, note))
            print("%-6s %6s %8s %8s" % (run, "-", "-", "no output"))
            continue
        if note == "trailing":
            trailing.append(fname)
        row = {
            "turns": j.get("num_turns", 0),
            "mins": j.get("duration_ms", 0) / 60000,
            "cost": j.get("total_cost_usd", 0),
            "ok": not j.get("is_error", False),
        }
        agg[cond].append(row)
        print("%-6s %6d %8.1f %8.3f" % (run, row["turns"], row["mins"], row["cost"]))

    print()
    print("%-6s %3s %8s %8s %6s %6s %8s %9s"
          % ("cond", "n", "mean", "median", "min", "max", "sd", "cost$"))
    total = 0.0
    for cond in sorted(agg):
        rows = agg[cond]
        n = len(rows)
        turns = sorted(r["turns"] for r in rows)
        cost = sum(r["cost"] for r in rows)
        total += cost
        print("%-6s %3d %8.1f %8.1f %6d %6d %8.1f %9.2f"
              % (cond, n, statistics.mean(turns), statistics.median(turns),
                 turns[0], turns[-1],
                 statistics.stdev(turns) if n > 1 else 0.0, cost))
    print("\nall runs: $%.2f" % total)
    if "time-perception-v3" in os.path.normpath(outdir):
        print("\nTurn counts are right-skewed: every condition floors near the same value\n"
              "and differs only in its tail, so means move on outliers. Read the median\n"
              "and spread alongside them. The headline comparison is not either of these\n"
              "numbers by eye - it is the pre-registered test in REPLICATION.md\n"
              "(one-tailed permutation Mann-Whitney, B vs pooled A+C, p = 0.657).\n"
              "Wall-clock means are not a metric of record: a machine-sleep hang during\n"
              "the run inflates B. Turns, cost and completion are unaffected.")
    if trailing:
        print("note: trailing bytes after the valid object in %s (first object used)"
              % ", ".join(trailing))
    if skipped:
        print("note: %d run(s) produced no usable output and are excluded from the\n"
              "      aggregates above, not counted as zeros: %s"
              % (len(skipped), ", ".join(skipped)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/time-perception-v3")
