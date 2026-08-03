#!/usr/bin/env python3
"""dog-years proprioception loop.

Gives Claude a clock by measuring what it actually does:
  event    — hook entry point; logs prompt/tool/stop events from stdin JSON
  predict  — record an estimate before starting work:  dog.py predict <slug> <calls lo-hi> <minutes lo-hi>
  resolve  — record completion:                        dog.py resolve <slug>
  report   — print calibration table + stats from measured history
  table    — splice the report into SKILL.md between the auto markers

Data lives in $DOG_YEARS_DATA (default ~/.claude/dog-years/), shared across
projects so calibration data accumulates. Events carry cwd so parallel
sessions (Conductor) don't cross-contaminate tool counts.

Must never break a session: every entry point swallows errors and exits 0.
"""
import json
import os
import sys
import time

DATA = os.environ.get("DOG_YEARS_DATA") or os.path.expanduser("~/.claude/dog-years")
SKILL_MD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SKILL.md")
MARK_START = "<!-- calibration:auto:start -->"
MARK_END = "<!-- calibration:auto:end -->"


def _append(fname, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, fname), "a") as f:
        f.write(json.dumps(obj) + "\n")


def _load(fname):
    path = os.path.join(DATA, fname)
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def cmd_event():
    h = json.load(sys.stdin)
    kind = {"PostToolUse": "tool", "UserPromptSubmit": "prompt", "Stop": "stop"}.get(
        h.get("hook_event_name", "")
    )
    if not kind:
        return
    rec = {
        "ts": time.time(),
        "event": kind,
        "cwd": h.get("cwd", ""),
        "session": h.get("session_id", ""),
    }
    if kind == "tool":
        rec["tool"] = h.get("tool_name", "")
    _append("events.jsonl", rec)


def _parse_range(s):
    s = s.replace("–", "-")
    parts = [p for p in s.split("-") if p != ""]
    lo = float(parts[0])
    hi = float(parts[1]) if len(parts) > 1 else lo
    return [lo, hi]


def cmd_predict(args):
    slug, calls, minutes = args[0], _parse_range(args[1]), _parse_range(args[2])
    _append("predictions.jsonl", {
        "type": "predict", "ts": time.time(), "slug": slug,
        "calls": calls, "minutes": minutes, "cwd": os.getcwd(),
    })
    print(f"predicted {slug}: {calls[0]:.0f}-{calls[1]:.0f} calls, {minutes[0]:.0f}-{minutes[1]:.0f} min")


def cmd_resolve(args):
    slug = args[0]
    _append("predictions.jsonl", {
        "type": "resolve", "ts": time.time(), "slug": slug, "cwd": os.getcwd(),
    })
    print(f"resolved {slug}")


def _rows():
    preds = _load("predictions.jsonl")
    events = _load("events.jsonl")
    resolves = [p for p in preds if p.get("type") == "resolve"]
    rows = []
    for p in [p for p in preds if p.get("type") == "predict"]:
        end_ts, inferred = None, False
        matches = [r for r in resolves if r["slug"] == p["slug"] and r["ts"] > p["ts"]]
        if matches:
            end_ts = min(m["ts"] for m in matches)
        else:
            stops = [e["ts"] for e in events
                     if e["event"] == "stop" and e.get("cwd") == p.get("cwd") and e["ts"] > p["ts"]]
            if stops:
                end_ts, inferred = min(stops), True
        if end_ts is None:
            continue  # still in progress
        calls = sum(1 for e in events
                    if e["event"] == "tool" and e.get("cwd") == p.get("cwd")
                    and p["ts"] < e["ts"] <= end_ts)
        mins = (end_ts - p["ts"]) / 60.0
        rows.append({
            "slug": p["slug"], "pred_calls": p["calls"], "pred_min": p["minutes"],
            "calls": calls, "min": mins, "inferred": inferred,
            "calls_hit": p["calls"][0] <= calls <= p["calls"][1],
            "min_hit": p["minutes"][0] <= mins <= p["minutes"][1],
        })
    return rows


def _fmt_report(rows):
    if not rows:
        return "No resolved predictions yet — no measured data.\n"
    lines = [
        "| task | pred calls | actual | pred min | actual | bracketed |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        brk = ("calls " if r["calls_hit"] else "") + ("min" if r["min_hit"] else "")
        lines.append(
            f"| {r['slug']}{' *' if r['inferred'] else ''} "
            f"| {r['pred_calls'][0]:.0f}-{r['pred_calls'][1]:.0f} | {r['calls']} "
            f"| {r['pred_min'][0]:.0f}-{r['pred_min'][1]:.0f} | {r['min']:.1f} "
            f"| {brk.strip() or 'none'} |"
        )
    n = len(rows)
    ratios = sorted(
        r["min"] / ((r["pred_min"][0] + r["pred_min"][1]) / 2)
        for r in rows if (r["pred_min"][0] + r["pred_min"][1]) > 0
    )
    med = ratios[len(ratios) // 2] if ratios else 0
    lines.append("")
    lines.append(
        f"n={n} · minutes bracketed {sum(r['min_hit'] for r in rows)}/{n} "
        f"· calls bracketed {sum(r['calls_hit'] for r in rows)}/{n} "
        f"· median actual/predicted-midpoint time ratio {med:.2f} "
        f"({'over' if med < 1 else 'under'}-estimating)"
    )
    lines.append("(* = end inferred from Stop event, no explicit resolve)")
    return "\n".join(lines) + "\n"


def cmd_report():
    sys.stdout.write(_fmt_report(_rows()))


def cmd_table():
    block = _fmt_report(_rows())
    with open(SKILL_MD) as f:
        text = f.read()
    if MARK_START not in text or MARK_END not in text:
        print("markers not found in SKILL.md", file=sys.stderr)
        return
    head, rest = text.split(MARK_START, 1)
    _, tail = rest.split(MARK_END, 1)
    with open(SKILL_MD, "w") as f:
        f.write(head + MARK_START + "\n" + block + MARK_END + tail)
    print("SKILL.md calibration table updated")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]
    if cmd == "event":
        cmd_event()
    elif cmd == "predict" and len(args) >= 3:
        cmd_predict(args)
    elif cmd == "resolve" and len(args) >= 1:
        cmd_resolve(args)
    elif cmd == "report":
        cmd_report()
    elif cmd == "table":
        cmd_table()
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"dog.py: {e}", file=sys.stderr)
    sys.exit(0)
