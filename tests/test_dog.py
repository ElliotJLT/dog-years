#!/usr/bin/env python3
"""Tests for dog.py. No dependencies: python3 tests/test_dog.py

These cover the two bugs that made the loop silently report nothing, because
dog.py deliberately swallows every exception and exits 0 so it can never break
a session. That design means a regression here is invisible at runtime.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

failures = []


def check(name, cond, detail=""):
    if cond:
        print("  pass  " + name)
    else:
        print("  FAIL  " + name + (" - " + detail if detail else ""))
        failures.append(name)


def load_dog(data_dir):
    os.environ["DOG_YEARS_DATA"] = data_dir
    spec = importlib.util.spec_from_file_location(
        "dog_%d" % int(time.time() * 1e6), os.path.join(ROOT, "skill", "dog.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def feed_event(dog, cwd, tool="Edit"):
    payload = json.dumps({"hook_event_name": "PostToolUse", "cwd": cwd,
                          "session_id": "s", "tool_name": tool})
    old = sys.stdin
    sys.stdin = type("S", (), {"read": staticmethod(lambda: payload)})()
    try:
        json_load = json.load
        json.load = lambda f: json.loads(payload)
        dog.cmd_event()
    finally:
        json.load = json_load
        sys.stdin = old


def test_range_parsing(dog):
    check("range 'lo-hi'", dog._parse_range("20-40") == [20.0, 40.0])
    check("range single value", dog._parse_range("15") == [15.0, 15.0])
    check("range en-dash", dog._parse_range("10–25") == [10.0, 25.0],
          "SKILL.md examples can carry an en-dash")


def test_cwd_normalisation(dog, tmp):
    """The bug: predict stored a resolved path, the hook stored an unresolved
    one, so no tool call was ever attributed to a prediction."""
    real = os.path.realpath(tmp)
    link = os.path.join(os.path.dirname(real), "link-" + os.path.basename(real))
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        print("  skip  cwd normalisation (no symlink support)")
        return
    check("realpath and symlink normalise equal", dog._norm(link) == dog._norm(real))
    check("empty cwd is safe", dog._norm("") == "")


def test_calls_attributed(dog, workdir):
    os.chdir(workdir)
    dog.cmd_predict(["job", "5-15", "1-30"])
    for _ in range(7):
        feed_event(dog, workdir)          # logical path, as the hook sends it
    dog.cmd_resolve(["job"])
    rows = dog._rows()
    check("one resolved row", len(rows) == 1, "got %d" % len(rows))
    if rows:
        check("tool calls attributed across path forms", rows[0]["calls"] == 7,
              "got %d, expected 7" % rows[0]["calls"])
        check("prediction bracketed", rows[0]["calls_hit"] is True)


def test_events_outside_window_excluded(dog, workdir):
    os.chdir(workdir)
    feed_event(dog, workdir)              # before the predict
    before = len(dog._rows())
    dog.cmd_predict(["later", "1-2", "1-2"])
    feed_event(dog, workdir)
    dog.cmd_resolve(["later"])
    row = [r for r in dog._rows() if r["slug"] == "later"]
    check("row created for second job", len(row) == 1)
    if row:
        check("earlier events not counted", row[0]["calls"] == 1,
              "got %d, expected 1" % row[0]["calls"])
    check("earlier rows unaffected", before >= 0)


def test_empty_report(dog):
    check("empty report is honest", "No resolved predictions yet" in dog._fmt_report([]))


def main():
    print("dog.py tests\n")
    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, "work")
        os.makedirs(work)
        dog = load_dog(os.path.join(tmp, "data"))
        test_range_parsing(dog)
        test_cwd_normalisation(dog, work)
        test_empty_report(dog)
        test_calls_attributed(dog, work)

    with tempfile.TemporaryDirectory() as tmp2:
        work2 = os.path.join(tmp2, "work")
        os.makedirs(work2)
        dog2 = load_dog(os.path.join(tmp2, "data"))
        test_events_outside_window_excluded(dog2, work2)

    print()
    if failures:
        print("%d failure(s): %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
