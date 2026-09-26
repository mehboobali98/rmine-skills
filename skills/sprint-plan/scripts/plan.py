#!/usr/bin/env python3
"""Compare a Redmine version's remaining estimated work with each assignee's capacity.

    plan.py --project AssetManagement --version "Bucket for September 2026"
    plan.py --project X --version "Sprint 42" --estimates estimates/ \\
            --until 2026-09-30 --leave "Jane Doe=2" --holiday 2026-09-15 --json

Stdlib only; shells out to rmine, and reuses /calibrate's estimate parser and
time-entry totals so both skills read the corpus the same way.
"""
import argparse
import calendar
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "calibrate", "scripts"))
import actuals  # noqa: E402

# An /estimate file and Redmine's field further apart than this are flagged:
# one of them is stale, and the plan is only as good as whichever it used.
DISAGREEMENT = 0.25
TIGHT = 0.85
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
UNASSIGNED = "(unassigned)"


def working_days(start, until, weekend=("sat", "sun"), holidays=()):
    """Days from start to until inclusive that are neither weekend nor holiday."""
    off = {WEEKDAYS.index(d) for d in weekend}
    days, d = 0, start
    while d <= until:
        if d.weekday() not in off and d not in holidays:
            days += 1
        d += timedelta(days=1)
    return days


def pick_estimate(from_file, from_redmine):
    """(hours, source, disagrees) for a ticket. The committed /estimate file is
    the reviewed number, so it wins; Redmine's field is the fallback."""
    if from_file is not None:
        disagrees = bool(from_redmine) and abs(from_file - from_redmine) > DISAGREEMENT * max(from_file, from_redmine)
        return from_file, "estimate file", disagrees
    if from_redmine:
        return from_redmine, "redmine", False
    return None, None, False


def rmine(args, profile=None):
    cmd = ["rmine", *args, "-o", "json"]
    if profile:
        cmd += ["--profile", profile]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "rmine exited %d" % proc.returncode)
    return json.loads(proc.stdout or "[]") or []


def plan(project, version, capacity_days, hours_per_day, leave, file_estimates, profile=None):
    issues = rmine(["issue", "list", "--project", project, "--version", version, "--status", "open", "--all"], profile)

    rows = []
    for iss in issues:
        hours, source, disagrees = pick_estimate(file_estimates.get(str(iss["id"])), iss.get("estimated_hours"))
        rows.append({
            "id": iss["id"],
            "subject": iss.get("subject", ""),
            "status": (iss.get("status") or {}).get("name", "?"),
            "assignee": (iss.get("assigned_to") or {}).get("name") or UNASSIGNED,
            "estimate": hours,
            "source": source,
            "redmine_estimate": iss.get("estimated_hours"),
            "disagrees": disagrees,
        })

    estimated = [r for r in rows if r["estimate"] is not None]
    with ThreadPoolExecutor(max_workers=8) as pool:
        spent = list(pool.map(lambda r: actuals.logged_hours(str(r["id"]), profile)[0], estimated))
    for r, s in zip(estimated, spent):
        r["spent"] = s
        r["remaining"] = max(r["estimate"] - s, 0.0)
        r["overrun"] = s > r["estimate"]

    people = {}
    for r in rows:
        p = people.setdefault(r["assignee"], {"name": r["assignee"], "tickets": 0, "unestimated": 0, "remaining": 0.0})
        p["tickets"] += 1
        if r["estimate"] is None:
            p["unestimated"] += 1
        else:
            p["remaining"] += r["remaining"]
    for p in people.values():
        if p["name"] == UNASSIGNED:
            p["capacity"] = None
            p["load"] = None
            p["verdict"] = "no one to do it"
            continue
        days = max(capacity_days - leave.get(p["name"], 0), 0)
        p["capacity"] = days * hours_per_day
        p["load"] = p["remaining"] / p["capacity"] if p["capacity"] else None
        if p["load"] is None:
            p["verdict"] = "no capacity"
        elif p["load"] > 1:
            p["verdict"] = "over"
        elif p["load"] > TIGHT:
            p["verdict"] = "tight"
        else:
            p["verdict"] = "ok"
        if p["unestimated"]:
            if p["verdict"] != "over":
                p["verdict"] = "unknown"
            p["verdict"] += ", %d unestimated" % p["unestimated"]

    assigned = [p for p in people.values() if p["capacity"] is not None]
    return {
        "people": sorted(people.values(), key=lambda p: (p["load"] is None, -(p["load"] or 0))),
        "team": {
            "tickets": len(rows),
            "estimated": len(estimated),
            "remaining": sum(p["remaining"] for p in people.values()),
            "capacity": sum(p["capacity"] for p in assigned),
        },
        "unestimated": [r for r in rows if r["estimate"] is None],
        "disagreements": [r for r in rows if r["disagrees"]],
        "overruns": [r for r in estimated if r["overrun"]],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--version", required=True, help="target version (sprint or bucket) name or ID")
    ap.add_argument("--estimates", action="append", default=[], help="/estimate files or folder (repeatable)")
    ap.add_argument("--from", dest="start", default=date.today().isoformat(), help="first day of capacity (default today)")
    ap.add_argument("--until", help="last day of capacity (default end of the --from month)")
    ap.add_argument("--hours-per-day", type=float, default=8)
    ap.add_argument("--weekend", default="sat,sun", help="non-working weekdays (default sat,sun)")
    ap.add_argument("--holiday", action="append", default=[], help="non-working date YYYY-MM-DD (repeatable)")
    ap.add_argument("--leave", action="append", default=[], metavar="NAME=DAYS", help="leave days in the period, by Redmine name (repeatable)")
    ap.add_argument("--profile")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    until = (datetime.strptime(args.until, "%Y-%m-%d").date() if args.until
             else start.replace(day=calendar.monthrange(start.year, start.month)[1]))
    if until < start:
        ap.error("--until is before --from")
    holidays = {datetime.strptime(h, "%Y-%m-%d").date() for h in args.holiday}
    weekend = [d.strip().lower()[:3] for d in args.weekend.split(",") if d.strip()]
    if any(d not in WEEKDAYS for d in weekend):
        ap.error("--weekend takes day names, e.g. sat,sun")
    leave = {}
    for pair in args.leave:
        name, _, days = pair.rpartition("=")
        try:
            leave[name.strip()] = float(days)
        except ValueError:
            ap.error("--leave takes NAME=DAYS, got %r" % pair)

    days = working_days(start, until, weekend, holidays)
    file_estimates = actuals.collect(args.estimates) if args.estimates else {}
    result = plan(args.project, args.version, days, args.hours_per_day, leave, file_estimates, args.profile)
    result["period"] = {"from": start.isoformat(), "until": until.isoformat(), "working_days": days,
                        "hours_per_day": args.hours_per_day}
    unknown = sorted(set(leave) - {p["name"] for p in result["people"]})
    result["unknown_leave_names"] = unknown

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    per = result["period"]
    print("%s to %s: %d working days x %gh" % (per["from"], per["until"], per["working_days"], per["hours_per_day"]))
    print("%-24s %7s %5s %9s %8s %6s  %s" % ("ASSIGNEE", "TICKETS", "NO EST", "REMAINING", "CAPACITY", "LOAD", "VERDICT"))
    for p in result["people"]:
        cap = "-" if p["capacity"] is None else "%.1fh" % p["capacity"]
        load = "-" if p["load"] is None else "%d%%" % round(p["load"] * 100)
        print("%-24s %7d %5d %8.1fh %8s %6s  %s" % (p["name"][:24], p["tickets"], p["unestimated"], p["remaining"], cap, load, p["verdict"]))
    t = result["team"]
    print("\nteam: %d tickets, %d estimated, %.1fh remaining against %.1fh capacity"
          % (t["tickets"], t["estimated"], t["remaining"], t["capacity"]))
    for label, key in (("disagree with Redmine", "disagreements"), ("over their estimate", "overruns")):
        if result[key]:
            print("%d tickets %s: %s" % (len(result[key]), label, ", ".join("#%d" % r["id"] for r in result[key])))
    if unknown:
        print("leave given for names not in this version: %s" % ", ".join(unknown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
