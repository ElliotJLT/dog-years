#!/bin/bash
# Exp 6 — belief-affordance control: are task-relevant (false) beliefs read,
# while time-beliefs are inert? F injects "half already modernized" (false).
set -u
MODEL="claude-haiku-4-5-20251001"
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$EXP_DIR/../skill" && pwd)"
OUT="$EXP_DIR/eval-results/exp6-belief"
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

BASE="Modernize the JavaScript in this repo: replace var declarations with const or let, and convert the callback-style code to async/await (wrap setTimeout in a Promise). Keep module.exports working.COND When finished, summarize what you changed."
FRAME_A=""
FRAME_F=" For context: about half of these files were already modernized by a previous run; the rest still need doing."

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
      --allowedTools "Bash,Edit,Write,Read,Glob,Grep" --max-turns 120 \
      --output-format json > "$OUT/$cond$rep.json" 2> "$OUT/$cond$rep.err")
  echo "$dir" > "$OUT/$cond$rep.dir"
}

for rep in 1 2 3 4 5 6; do
  run_one A "$rep" "$FRAME_A" &
  run_one F "$rep" "$FRAME_F" &
  wait
done

python3 - "$OUT" <<'EOF'
import json, os, re, glob, sys
out = sys.argv[1]
agg = {}
for path in sorted(glob.glob(os.path.join(out, "*.json"))):
    run = os.path.basename(path).replace(".json", "")
    dirf = os.path.join(out, run + ".dir")
    if os.path.getsize(path) == 0 or not os.path.exists(dirf): continue
    j = json.load(open(path))
    rundir = open(dirf).read().strip()
    done = sum(1 for f in glob.glob(os.path.join(rundir, "module*.js"))
               if not re.search(r"\bvar\s", open(f).read()) and "async" in open(f).read())
    pre_edit_inspect, seen_edit, calls = 0, False, 0
    ev = os.path.join(rundir, ".dogdata", "events.jsonl")
    if os.path.exists(ev):
        for line in open(ev):
            e = json.loads(line); calls += 1
            t = e.get("tool", "")
            if t in ("Edit", "Write"): seen_edit = True
            elif not seen_edit and t in ("Read", "Glob", "Grep", "Bash"): pre_edit_inspect += 1
    text = j.get("result", "") or ""
    reconciled = bool(re.search(r"(all 20|all twenty|every (file|module)|none .{0,30}(modern|converted|done)|actually|in fact|contrary|however, (all|every))", text, re.I))
    agg.setdefault(run[0], []).append(dict(run=run, done=done, pre=pre_edit_inspect, calls=calls,
                                           turns=j.get("num_turns", 0), rec=reconciled))
    print(f"{run}: files {done}/20 · pre-edit inspections {pre_edit_inspect} · calls {calls} · turns {j.get('num_turns',0)} · reconciles-false-claim={reconciled}")
print()
for c in "AF":
    rows = agg.get(c, [])
    if rows:
        n = len(rows)
        m = lambda k: sum(r[k] for r in rows) / n
        print(f"cond {c}: mean files {m('done'):.1f}/20 · pre-edit inspections {m('pre'):.1f} · calls {m('calls'):.1f} · turns {m('turns'):.1f} · reconciled {sum(r['rec'] for r in rows)}/{n}")
EOF
echo "fixtures in $ROOT"
