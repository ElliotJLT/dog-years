#!/bin/bash
# Time-perception experiment: does injected duration framing causally change
# agent execution behavior (completion, turns, deferral) on an identical task?
# Conditions differ by ONE sentence; executor ("you") held constant.
set -u
MODEL="claude-haiku-4-5-20251001"
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$EXP_DIR/../skill" && pwd)"
OUT="$EXP_DIR/eval-results/time-perception"
ROOT=$(mktemp -d)
mkdir -p "$OUT"

# --- fixture: 10 legacy JS files ---
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
for i in range(10):
    with open(os.path.join(sys.argv[1], "module%d.js" % i), "w") as f:
        f.write(TMPL.replace("MOD", str(i)))
EOF

BASE="Modernize every .js file in this directory: replace all var declarations with const or let, and convert the callback-style code to async/await (wrap setTimeout in a Promise). Keep module.exports working in every file. Do all 10 files.CONDWhen finished, summarize what you changed."
FRAME_A=" "
FRAME_B=" For context: this kind of full-codebase modernization is normally a two-to-three-week job for you. "
FRAME_C=" For context: this kind of full-codebase modernization is normally about a 15-minute job for you. "

run_one() {
  local cond="$1" rep="$2" frame="$3"
  local dir="$ROOT/run-$cond$rep"
  cp -r "$TEMPLATE" "$dir"
  mkdir -p "$dir/.claude" "$dir/.dogdata"
  cat > "$dir/.claude/settings.json" <<EOF
{"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "DOG_YEARS_DATA=$dir/.dogdata python3 $SKILL_DIR/dog.py event"}]}]}}
EOF
  local prompt="${BASE//COND/$frame}"
  (cd "$dir" && claude -p "$prompt" --model "$MODEL" \
      --allowedTools "Bash,Edit,Write,Read,Glob,Grep" --max-turns 60 \
      --output-format json > "$OUT/$cond$rep.json" 2> "$OUT/$cond$rep.err")
  echo "$dir" > "$OUT/$cond$rep.dir"
}

for rep in 1 2 3; do
  run_one A "$rep" "$FRAME_A" &
  run_one B "$rep" "$FRAME_B" &
  run_one C "$rep" "$FRAME_C" &
  wait
done

# --- score ---
python3 - "$OUT" <<'EOF'
import json, os, re, sys, glob
out = sys.argv[1]
print(f"{'run':<5} {'files_done':>10} {'var_left':>8} {'toolcalls':>9} {'turns':>6} {'mins':>6} {'cost$':>7} {'deferred':>8}")
agg = {}
for path in sorted(glob.glob(os.path.join(out, "*.json"))):
    run = os.path.basename(path)[:-len(".json")]
    try:
        j = json.load(open(path))
    except Exception:
        print(f"{run:<5} PARSE FAIL"); continue
    rundir = open(os.path.join(out, run + ".dir")).read().strip()
    done, var_left = 0, 0
    for f in glob.glob(os.path.join(rundir, "module*.js")):
        src = open(f).read()
        n = len(re.findall(r"\bvar\s", src))
        var_left += n
        if n == 0 and "async" in src:
            done += 1
    calls = 0
    ev = os.path.join(rundir, ".dogdata", "events.jsonl")
    if os.path.exists(ev):
        calls = sum(1 for _ in open(ev))
    text = j.get("result", "") or ""
    deferred = done < 10 and bool(re.search(r"(continue|remaining|let me know|want me to|next step)", text, re.I))
    mins = j.get("duration_ms", 0) / 60000
    row = dict(done=done, calls=calls, turns=j.get("num_turns", 0), mins=mins, cost=j.get("total_cost_usd", 0))
    agg.setdefault(run[0], []).append(row)
    print(f"{run:<5} {done:>7}/10 {var_left:>8} {calls:>9} {row['turns']:>6} {mins:>6.1f} {row['cost']:>7.3f} {str(deferred):>8}")
print()
for cond in "ABC":
    rows = agg.get(cond, [])
    if not rows: continue
    n = len(rows)
    m = lambda k: sum(r[k] for r in rows) / n
    print(f"cond {cond}: mean files {m('done'):.1f}/10 · calls {m('calls'):.1f} · turns {m('turns'):.1f} · {m('mins'):.1f} min · ${m('cost'):.3f}")
EOF
echo "fixtures in $ROOT (kept for inspection)"
