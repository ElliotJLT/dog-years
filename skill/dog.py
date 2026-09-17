#!/usr/bin/env python3
"""dog-years proprioception loop.

Gives Claude a clock by measuring what it actually does:
  event    — hook entry point; logs prompt/tool/stop events from stdin JSON
  predict  — record an estimate before starting work:  dog.py predict <slug> <calls lo-hi> <minutes lo-hi>
  resolve  — record completion:                        dog.py resolve <slug>
  report   — print calibration table + stats from measured history
  table    — splice the report into SKILL.md between the auto markers
  doctor   — check the install is wired up (hook firing, data dir, markers)
  install-hooks   — register the event hooks in ~/.claude/settings.json (idempotent)
  uninstall-hooks — remove them again

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
SELF = os.path.abspath(__file__)
SETTINGS = os.environ.get("DOG_YEARS_SETTINGS") or os.path.expanduser("~/.claude/settings.json")
HOOK_EVENTS = {"UserPromptSubmit": None, "PostToolUse": "*", "Stop": None}
MARK_START = "<!-- calibration:auto:start -->"
MARK_END = "<!-- calibration:auto:end -->"


def _norm(path):
    """Resolve symlinks so a physical and a logical path compare equal.

    predict/resolve record os.getcwd(), which resolves symlinks. The hook
    records Claude Code's cwd, which may not. Under any symlinked directory
    (macOS /tmp, git worktrees) the two never matched and tool counts read 0.
    """
    try:
        return os.path.realpath(path) if path else ""
    except OSError:
        return path or ""


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
        "cwd": _norm(h.get("cwd", "")),
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
        "calls": calls, "minutes": minutes, "cwd": _norm(os.getcwd()),
    })
    print(f"predicted {slug}: {calls[0]:.0f}-{calls[1]:.0f} calls, {minutes[0]:.0f}-{minutes[1]:.0f} min")


def cmd_resolve(args):
    slug = args[0]
    _append("predictions.jsonl", {
        "type": "resolve", "ts": time.time(), "slug": slug, "cwd": _norm(os.getcwd()),
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
                     if e["event"] == "stop" and _norm(e.get("cwd", "")) == _norm(p.get("cwd", ""))
                     and e["ts"] > p["ts"]]
            if stops:
                end_ts, inferred = min(stops), True
        if end_ts is None:
            continue  # still in progress
        calls = sum(1 for e in events
                    if e["event"] == "tool"
                    and _norm(e.get("cwd", "")) == _norm(p.get("cwd", ""))
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


def _is_ours(entry):
    return any("dog.py event" in (h.get("command") or "")
               for h in entry.get("hooks", []) if isinstance(h, dict))


def _read_settings():
    if not os.path.exists(SETTINGS):
        return {}
    with open(SETTINGS) as f:
        raw = f.read()
    return json.loads(raw) if raw.strip() else {}


def _write_settings(data):
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    if os.path.exists(SETTINGS):
        with open(SETTINGS) as f:
            backup = f.read()
        with open(SETTINGS + ".dog-years.bak", "w") as f:
            f.write(backup)
    with open(SETTINGS, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def cmd_install_hooks():
    """Merge our three hooks into settings.json without touching anything else.

    Re-running replaces any earlier dog-years entry (so a moved install gets
    the new path) and leaves every other hook alone.
    """
    data = _read_settings()
    hooks = data.setdefault("hooks", {})
    cmd = "python3 %s event" % SELF
    for event, matcher in HOOK_EVENTS.items():
        entries = [e for e in hooks.get(event, []) if not _is_ours(e)]
        entry = {"hooks": [{"type": "command", "command": cmd}]}
        if matcher is not None:
            entry["matcher"] = matcher
        entries.append(entry)
        hooks[event] = entries
    _write_settings(data)
    print("hooks registered in %s for %s" % (SETTINGS, ", ".join(HOOK_EVENTS)))
    print("command: %s" % cmd)
    print("start a new Claude Code session for them to take effect")


def cmd_uninstall_hooks():
    data = _read_settings()
    hooks = data.get("hooks", {})
    removed = 0
    for event in list(hooks):
        kept = [e for e in hooks[event] if not _is_ours(e)]
        removed += len(hooks[event]) - len(kept)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks and "hooks" in data:
        del data["hooks"]
    _write_settings(data)
    print("removed %d dog-years hook entr%s from %s"
          % (removed, "y" if removed == 1 else "ies", SETTINGS))


def _hook_status():
    """(registered, path_exists, missing_events)"""
    try:
        hooks = _read_settings().get("hooks", {})
    except (OSError, ValueError):
        return False, False, list(HOOK_EVENTS)
    missing, path_ok = [], True
    for event in HOOK_EVENTS:
        ours = [e for e in hooks.get(event, []) if _is_ours(e)]
        if not ours:
            missing.append(event)
            continue
        for e in ours:
            for h in e.get("hooks", []):
                target = (h.get("command") or "").replace("python3 ", "", 1).rsplit(" event", 1)[0]
                if target and not os.path.exists(os.path.expanduser(target)):
                    path_ok = False
    return len(missing) < len(HOOK_EVENTS), path_ok, missing


def cmd_doctor():
    """Check the install is actually wired up.

    Every entry point here swallows errors and exits 0 so a broken hook can
    never break a session. The cost of that is silent failure: the hook path
    was wrong for the life of the project and nothing ever said so.
    """
    ok, warn = [], []

    try:
        os.makedirs(DATA, exist_ok=True)
        probe = os.path.join(DATA, ".probe")
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        ok.append(f"data dir writable: {DATA}")
    except OSError as e:
        warn.append(f"data dir NOT writable ({DATA}): {e}")

    registered, path_ok, missing = _hook_status()
    if not registered:
        warn.append("no dog-years hooks in %s - run: python3 %s install-hooks"
                    % (SETTINGS, SELF))
    elif missing:
        warn.append("hooks registered for some events but not %s - re-run install-hooks"
                    % ", ".join(missing))
    elif not path_ok:
        warn.append("a registered hook points at a dog.py that does not exist - "
                    "re-run install-hooks from the current install")
    else:
        ok.append("hooks registered for %s" % ", ".join(HOOK_EVENTS))

    events = _load("events.jsonl")
    tools = [e for e in events if e.get("event") == "tool"]
    if not events:
        warn.append("no events logged yet" + (
            " - hooks are registered, so start a new session and run a tool"
            if registered and path_ok else ""))
    else:
        age_h = (time.time() - max(e["ts"] for e in events)) / 3600
        ok.append(f"{len(events)} events logged ({len(tools)} tool calls), "
                  f"most recent {age_h:.1f}h ago")

    preds = _load("predictions.jsonl")
    open_preds = {p["slug"] for p in preds if p.get("type") == "predict"} - \
                 {p["slug"] for p in preds if p.get("type") == "resolve"}
    rows = _rows()
    ok.append(f"{len(preds)} prediction records, {len(rows)} resolved, "
              f"{len(open_preds)} still open")
    if rows and all(r["calls"] == 0 for r in rows) and tools:
        warn.append("every resolved prediction shows 0 tool calls despite logged "
                    "events - predictions and events disagree on working directory")

    if os.path.exists(SKILL_MD):
        text = open(SKILL_MD).read()
        if MARK_START in text and MARK_END in text:
            ok.append("SKILL.md calibration markers present")
        else:
            warn.append(f"SKILL.md missing calibration markers: {SKILL_MD}")
    else:
        warn.append(f"SKILL.md not found next to dog.py: {SKILL_MD}")

    for line in ok:
        print("  ok   " + line)
    for line in warn:
        print("  WARN " + line)
    if not warn:
        print("\nAll checks passed. Run a task, then `dog.py report`.")
    else:
        print("\n%d problem(s). The loop will look empty until these are fixed."
              % len(warn))


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
    elif cmd == "doctor":
        cmd_doctor()
    elif cmd == "install-hooks":
        cmd_install_hooks()
    elif cmd == "uninstall-hooks":
        cmd_uninstall_hooks()
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"dog.py: {e}", file=sys.stderr)
    sys.exit(0)
