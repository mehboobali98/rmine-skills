#!/usr/bin/env python3
"""Tests for plan.py. Run with: python3 test_plan.py

Stdlib only, no test runner needed. rmine is faked by replacing
subprocess.run, which both plan.py and the actuals.py it reuses call.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_working_days():
    mon, fri, sun = date(2026, 9, 28), date(2026, 10, 2), date(2026, 10, 4)
    check("one working week", plan.working_days(mon, fri), 5)
    check("weekend skipped", plan.working_days(mon, sun), 5)
    check("holiday skipped", plan.working_days(mon, fri, holidays={date(2026, 9, 30)}), 4)
    check("fri-sat weekend", plan.working_days(mon, sun, weekend=("fri", "sat")), 5)


def test_pick_estimate():
    check("file wins", plan.pick_estimate(10.0, 12.0), (10.0, "estimate file", False))
    check("far apart flagged", plan.pick_estimate(10.0, 20.0), (10.0, "estimate file", True))
    check("redmine fallback", plan.pick_estimate(None, 6.0), (6.0, "redmine", False))
    check("no estimate", plan.pick_estimate(None, None), (None, None, False))
    check("zero is no estimate", plan.pick_estimate(None, 0), (None, None, False))


ISSUES = [
    {"id": 1, "subject": "a", "assigned_to": {"name": "Jane"}, "estimated_hours": 30},
    {"id": 2, "subject": "b", "assigned_to": {"name": "Jane"}, "estimated_hours": 10},
    {"id": 3, "subject": "c", "assigned_to": {"name": "Omar"}, "estimated_hours": 8},
    {"id": 4, "subject": "d", "assigned_to": {"name": "Omar"}},
    {"id": 5, "subject": "e", "assigned_to": {"name": "Lena"}, "estimated_hours": 2},
    {"id": 6, "subject": "f"},
]
TIME = {
    "1": [{"hours": 5, "activity": {"name": "Development"}, "user": {"name": "Jane"}},
          {"hours": 8, "activity": {"name": "Leave"}, "user": {"name": "Jane"}}],
    "3": [{"hours": 12, "activity": {"name": "Development"}, "user": {"name": "Omar"}}],
}


def fake_run(cmd, **kwargs):
    if cmd[1:3] == ["issue", "list"]:
        out = ISSUES
    elif cmd[1:3] == ["time", "list"]:
        out = TIME.get(cmd[cmd.index("--issue") + 1], [])
    else:
        raise AssertionError("unexpected command %r" % cmd)
    return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(out), stderr="")


def run_plan(**kw):
    original = subprocess.run
    subprocess.run = fake_run
    try:
        args = dict(capacity_days=5, hours_per_day=8, leave={}, file_estimates={})
        args.update(kw)
        return plan.plan("P", "Sprint", **args)
    finally:
        subprocess.run = original


def test_plan():
    result = run_plan(leave={"Jane": 1})
    people = {p["name"]: p for p in result["people"]}

    check("leave on a ticket is not work", people["Jane"]["remaining"], 25 + 10)
    check("leave shrinks capacity", people["Jane"]["capacity"], 32)
    check("over capacity", people["Jane"]["verdict"], "over")
    check("overrun floors at zero", people["Omar"]["remaining"], 0)
    check("unestimated makes load unknown", people["Omar"]["verdict"], "unknown, 1 unestimated")
    check("light load is ok", people["Lena"]["verdict"], "ok")
    check("unassigned has no capacity", people[plan.UNASSIGNED]["verdict"], "no one to do it")
    check("overruns listed", [r["id"] for r in result["overruns"]], [3])
    check("unestimated listed", sorted(r["id"] for r in result["unestimated"]), [4, 6])
    check("team capacity excludes unassigned", result["team"]["capacity"], 32 + 40 + 40)
    check("busiest first", result["people"][0]["name"], "Jane")
    check("each person's tickets, largest first", [i["id"] for i in people["Jane"]["items"]], [1, 2])
    check("unestimated ticket carries no numbers", people["Omar"]["items"][1]["remaining"], None)


def test_estimate_file_overrides_redmine():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "estimate-2.md")
        with open(path, "w") as f:
            f.write("Redmine: https://pm.example.com/issues/2\n\nTotal (24 hrs ~ 6 points)\n")
        files = plan.actuals.collect([d])
    result = run_plan(file_estimates=files)
    jane = next(p for p in result["people"] if p["name"] == "Jane")
    check("file estimate used", jane["remaining"], 25 + 24)
    check("disagreement flagged", [r["id"] for r in result["disagreements"]], [2])


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    if FAILURES:
        print("FAILED — plan.py")
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)
    print("ok — plan.py")


if __name__ == "__main__":
    main()
