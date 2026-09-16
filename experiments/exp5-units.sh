#!/bin/bash
# Exp 5 — unit elicitation: is the time-delusion bound to the unit?
# T: estimate in minutes before starting. K: estimate in tool calls.
# Estimate is committed to ESTIMATE.txt pre-hoc; hooks measure actuals.
set -u
MODEL="claude-haiku-4-5-20251001"
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$EXP_DIR/../skill" && pwd)"
OUT="$EXP_DIR/eval-results/exp5-units"
ROOT=$(mktemp -d)
mkdir -p "$OUT"

TEMPLATE="$ROOT/template"
mkdir -p "$TEMPLATE"
python3 - "$TEMPLATE" <<'EOF'
import sys, os
TMPL = '''var count = 0;
var label = "modMOD";

function loadMOD(id, callback) {
  var result = { id: id, label: label };
  setTimeout(function () {
    if (!id) { callback(new Error("no id")); return; }
    count = count + 1;
    callback(null, result);
  }, 10);
}

function processMOD(items, callback) {
  var out = [];
  var done = 0;
  items.forEach(function (item) {
    loadMOD(item, function (err, res) {
      if (err) { callback(err); return; }
      out.push(res);
      done = done + 1;
      if (done === items.length) { callback(null, out); }
    });
  });
}

module.exports = { loadMOD: loadMOD, processMOD: processMOD };
'''
for i in range(20):
    with open(os.path.join(sys.argv[1], "module%d.js" % i), "w") as f:
        f.write(TMPL.replace("MOD", str(i)))
EOF

TASK="modernizing the JavaScript in this repo: replace var declarations with const or let, and convert the callback-style code to async/await (wrap setTimeout in a Promise). Keep module.exports working."
ASK_T="Before doing anything else, write a file ESTIMATE.txt containing one line in the format 'ESTIMATE: X-Y minutes' — your honest estimate of how long the whole job will take you. Then do the job of $TASK When finished, summarize what you changed."
ASK_K="Before doing anything else, write a file ESTIMATE.txt containing one line in the format 'ESTIMATE: X-Y tool calls' — your honest estimate of how many tool calls the whole job will take you. Then do the job of $TASK When finished, summarize what you changed."

run_one() {
  local cond="$1" rep="$2" prompt="$3"
  local dir="$ROOT/run-$cond$rep"
  cp -r "$TEMPLATE" "$dir"
  mkdir -p "$dir/.claude" "$dir/.dogdata"
  cat > "$dir/.claude/settings.json" <<EOF
{"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "DOG_YEARS_DATA=$dir/.dogdata python3 $SKILL_DIR/dog.py event"}]}]}}
EOF
  (cd "$dir" && claude -p "$prompt" --model "$MODEL" \
      --allowedTools "Bash,Edit,Write,Read,Glob,Grep" --max-turns 120 \
      --output-format json > "$OUT/$cond$rep.json" 2> "$OUT/$cond$rep.err")
  echo "$dir" > "$OUT/$cond$rep.dir"
}

for rep in 1 2 3 4 5 6; do
  run_one T "$rep" "$ASK_T" &
  run_one K "$rep" "$ASK_K" &
  wait
done

python3 - "$OUT" <<'EOF'
import json, os, re, glob, sys, math
out = sys.argv[1]
agg = {}
for path in sorted(glob.glob(os.path.join(out, "*.json"))):
    run = os.path.basename(path).replace(".json", "")
    dirf = os.path.join(out, run + ".dir")
    if os.path.getsize(path) == 0 or not os.path.exists(dirf): continue
    j = json.load(open(path))
    rundir = open(dirf).read().strip()
    est_path = os.path.join(rundir, "ESTIMATE.txt")
    est = open(est_path).read() if os.path.exists(est_path) else ""
    nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", est)][:2]
    lo, hi = (nums + nums)[:2] if nums else (None, None)
    calls = 0
    ev = os.path.join(rundir, ".dogdata", "events.jsonl")
    if os.path.exists(ev):
        calls = sum(1 for _ in open(ev))
    mins = j.get("duration_ms", 0) / 60000
    done = sum(1 for f in glob.glob(os.path.join(rundir, "module*.js"))
               if not re.search(r"\bvar\s", open(f).read()) and "async" in open(f).read())
    actual = mins if run[0] == "T" else calls
    if lo is None:
        print(f"{run}: NO PARSEABLE ESTIMATE ({est!r})"); continue
    mid = (lo + hi) / 2
    bracket = lo <= actual <= hi
    logerr = abs(math.log((actual + 1e-9) / mid)) if mid > 0 else float("nan")
    agg.setdefault(run[0], []).append((run, lo, hi, actual, bracket, logerr))
    unit = "min" if run[0] == "T" else "calls"
    print(f"{run}: est {lo:.0f}-{hi:.0f} {unit} · actual {actual:.1f} · bracket={bracket} · |log err|={logerr:.2f} · files {done}/20 · ({calls} calls, {mins:.1f} min)")
print()
for c in "TK":
    rows = agg.get(c, [])
    if rows:
        n = len(rows)
        print(f"cond {c} ({'minutes' if c=='T' else 'tool calls'}): bracket {sum(r[4] for r in rows)}/{n} · mean |log err| {sum(r[5] for r in rows)/n:.2f}")
EOF
echo "fixtures in $ROOT"
