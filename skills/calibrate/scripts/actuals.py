#!/usr/bin/env python3
"""Compare estimated hours against hours actually logged in Redmine.

Reads estimate files (or any single file holding many estimates), pulls the
matching time entries via `rmine time list`, and reports the ratio per ticket
plus aggregate drift.

    actuals.py estimates/
    actuals.py estimates/estimate-54039.md
    actuals.py --json estimates/

Stdlib only; shells out to rmine for the API access and auth.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from statistics import median

# Time logged under these activities isn't work on the ticket. Redmine lets any
# activity be booked against any issue, and leave in particular shows up
# against whatever the person had open — counting it inflates every ratio.
NON_WORK_ACTIVITIES = {"leave", "holiday", "vacation", "sick", "public holiday"}

ISSUE_RE = re.compile(r"/issues/(\d+)")

# Total lines are hand-written and inconsistent. Observed shapes:
#   Total (16 hrs ~ 4 points)      Total: 4.25 hrs        Total ~ 11 hrs
#   Total (26.5 / 4 ~ 7 pts)       Total: 12 hrs ~ 3 points
#   Total: 19 + 6 + 60 = 44 ~ 11 points
#   Total (18.5 + 38.05 ~ 60 hrs = 15 points)
# And two decoys that are sub-details, not totals:
#   Total 16 actions               Total 17 relationships
NUM = r"(\d+(?:\.\d+)?)"
TOTAL_PATTERNS = [
    re.compile(NUM + r"\s*(?:hrs|hours|hr)\b", re.I),  # "60 hrs" wins outright
    re.compile(NUM + r"\s*/\s*4\b"),                   # "26.5 / 4 ~ 7 pts"
    re.compile(r"=\s*" + NUM + r"\s*~"),               # "= 44 ~ 11 points"
]


def parse_total(line):
    """Return the estimated hours on a Total line, or None."""
    body = line.strip()
    if not re.match(r"^Total\b", body, re.I):
        return None
    # A bare noun after the number means it's counting something else.
    if re.match(r"^Total\s+\d+\s+[a-z]", body, re.I):
        return None
    if not re.search(r"[:(~]|hrs|hours", body, re.I):
        return None
    for pattern in TOTAL_PATTERNS:
        m = pattern.search(body)
        if m:
            return float(m.group(1))
    return None


def parse_estimates(path):
    """Yield (issue_id, estimated_hours) for every estimate found in a file.

    Works for a single estimate file and for one file holding many:
    an issue URL claims every Total line until the next issue URL appears.
    """
    current = None
    with open(path) as f:
        for line in f:
            found = ISSUE_RE.search(line)
            if found:
                current = found.group(1)
                continue
            hours = parse_total(line)
            if hours is not None and current:
                yield current, hours
                current = None  # one total per issue; ignore stray later ones


def logged_hours(issue_id, profile=None):
    """Total hours logged against an issue, split into work and non-work."""
    cmd = ["rmine", "time", "list", "--issue", issue_id, "-o", "json"]
    if profile:
        cmd += ["--profile", profile]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"rmine exited {proc.returncode}")
    entries = json.loads(proc.stdout or "[]") or []

    work = nonwork = 0.0
    users = set()
    for e in entries:
        hours = float(e.get("hours") or 0)
        activity = (e.get("activity") or {}).get("name", "")
        if activity.strip().lower() in NON_WORK_ACTIVITIES:
            nonwork += hours
        else:
            work += hours
            users.add((e.get("user") or {}).get("name", "?"))
    return work, nonwork, len(users)


def issue_status(issue_id, profile=None):
    """The issue's status name, or '?'. A ticket still in flight has only
    partial hours logged, which reads as a low ratio and quietly drags the
    aggregate down — so the status belongs next to every row."""
    cmd = ["rmine", "issue", "view", issue_id, "-o", "json"]
    if profile:
        cmd += ["--profile", profile]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return "?"
    try:
        return (json.loads(proc.stdout).get("status") or {}).get("name", "?")
    except Exception:
        return "?"


def collect(paths):
    """Gather (issue_id, hours) from files and directories, newest wins."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(
                os.path.join(p, n) for n in os.listdir(p) if n.endswith(".md")
            )
        else:
            files.append(p)

    seen = {}
    for path in files:
        for issue_id, hours in parse_estimates(path):
            seen[issue_id] = hours
    return seen


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", help="an estimates/ directory, individual estimate files, or one file holding many")
    ap.add_argument("--profile", help="rmine profile to use")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    estimates = collect(args.paths)
    if not estimates:
        sys.exit("no estimates found — expected a Redmine issue URL and a Total line")

    rows, missing = [], []
    for issue_id, est in sorted(estimates.items(), key=lambda kv: int(kv[0])):
        try:
            work, nonwork, users = logged_hours(issue_id, args.profile)
        except Exception as e:
            missing.append((issue_id, est, f"error: {e}"))
            continue
        if work == 0:
            missing.append((issue_id, est, "no time logged"))
            continue
        rows.append({
            "issue": issue_id, "estimated": est, "actual": work,
            "ratio": work / est, "excluded": nonwork, "loggers": users,
            "status": issue_status(issue_id, args.profile),
        })

    if args.json:
        print(json.dumps({"rows": rows, "missing": [
            {"issue": i, "estimated": e, "reason": r} for i, e, r in missing]}, indent=2))
        return

    print(f"{'issue':>7} {'est':>7} {'actual':>7} {'ratio':>6} {'who':>4} "
          f"{'status':<12} notes")
    for r in rows:
        notes = []
        if r["excluded"]:
            notes.append(f"excluded {r['excluded']:g}h non-work")
        if r["ratio"] < 0.5:
            notes.append("suspect under-logging")
        print(f"{r['issue']:>7} {r['estimated']:>7g} {r['actual']:>7.1f} "
              f"{r['ratio']:>6.2f} {r['loggers']:>4} {r['status']:<12} "
              f"{', '.join(notes)}")

    for issue_id, est, reason in missing:
        print(f"{issue_id:>7} {est:>7g} {'—':>7} {'—':>6} {'—':>4} {'—':<12} {reason}")

    if not rows:
        sys.exit("\nno tickets had logged time — nothing to calibrate against")

    ratios = sorted(r["ratio"] for r in rows)
    total_est = sum(r["estimated"] for r in rows)
    total_act = sum(r["actual"] for r in rows)
    within = sum(1 for x in ratios if 0.75 <= x <= 1.25)

    print(f"\ncovered          {len(rows)} of {len(estimates)} tickets"
          f" ({len(missing)} without usable logged time)")
    print(f"weighted ratio   {total_act / total_est:.2f}  "
          f"({total_act:g}h actual / {total_est:g}h estimated)")
    print(f"median ratio     {median(ratios):.2f}")
    print(f"spread           {ratios[0]:.2f} – {ratios[-1]:.2f}")
    print(f"within +/-25%    {within} of {len(rows)}")
    print("\nThe weighted ratio is dominated by big tickets; the median is not.")
    print("When they disagree, the drift is not uniform — read the table, and")
    print("see SKILL.md before changing any anchor.")


if __name__ == "__main__":
    main()
