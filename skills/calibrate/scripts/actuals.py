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
# The `Redmine:` header names the ticket being estimated. Any other issue URL
# in the file is a reference, not the subject — `Assumptions:` routinely links
# the tickets treated as shipped foundations or dependencies, exactly as
# estimate/SKILL.md asks for. Those must never claim the Total. The `**` allows
# for the bold the header carries when the estimate came out of a rich-text doc.
REDMINE_HEADER_RE = re.compile(r"^\**\s*Redmine\s*\**\s*:\s*\S*/issues/(\d+)", re.I)
# `Mode:` says which column of the rubric an estimate was priced from. The two
# can sit more than twice apart for the same ticket, so they never share an
# aggregate. Estimates written before 0.9.0 have no Mode: line.
MODE_HEADER_RE = re.compile(r"^\**\s*Mode\s*\**\s*:\s*\**\s*(?P<mode>[A-Za-z-]+)", re.I)

# The calibration bar. A ticket below this fraction of its group's median is
# well below the rest, which is what under-logging looks like. Measuring it
# against 1.0 instead flagged every ticket of a team that steadily
# overestimates, and hid the drift this analysis exists to find (#9).
LOW_VS_REST = 0.5
MIN_TICKETS = 20

# Estimates are written as multi-level outlines and the numbering survives the
# export, so the Total arrives as "6. Total (16 hrs ~ 4 points)". Stripping the
# marker is what keeps a numbered estimate inside the corpus — unstripped, it
# parses as nothing and the ticket silently never existed.
MARKER_RE = re.compile(
    r"^(?:\d+|[a-zA-Z]|[ivxlcdm]{2,6}|[IVXLCDM]{2,6})[.)]\s+|^[-*\u2022]\s+"
)


def content(line):
    """A line's text with indentation and any outline marker removed."""
    return MARKER_RE.sub("", line.strip(), count=1)

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
    body = content(line)
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
    """Yield (issue_id, estimated_hours) for every estimate found in a file."""
    for issue_id, hours, _ in parse_estimate_records(path):
        yield issue_id, hours


def parse_estimate_records(path):
    """Yield (issue_id, estimated_hours, mode) for every estimate in a file.

    mode is the estimate's `Mode:` header, lower-cased, or None when the
    estimate has none. Works for a single estimate file and for one file
    holding many.

    A `Redmine:` header claims the Total that follows it, and nothing else can
    take it away. Older estimates that carry a bare issue URL instead still
    work — a bare URL claims the Total only while no header has been seen for
    the current estimate. Without that precedence a linked ticket named in
    `Assumptions:` silently steals the hours: the estimated ticket then reports
    `no time logged` and drops out of the corpus, while the linked one is
    compared against an estimate that was never for it.
    """
    current = None
    from_header = False
    mode = None
    with open(path) as f:
        for line in f:
            header = REDMINE_HEADER_RE.match(content(line))
            if header:
                current, from_header = header.group(1), True
                continue
            stated = MODE_HEADER_RE.match(content(line))
            if stated:
                mode = stated.group("mode").lower()
                continue
            found = ISSUE_RE.search(line)
            if found:
                if not from_header:
                    current = found.group(1)
                continue
            hours = parse_total(line)
            if hours is not None and current:
                yield current, hours, mode
                # One total per issue; the next estimate re-establishes all three.
                current, from_header, mode = None, False, None


def logged_hours(issue_id, profile=None):
    """Total hours logged against an issue, split into work and non-work."""
    # --all matters: `rmine time list` returns 25 entries by default, and a
    # ticket that ran for weeks has more than that. Without it the hours come
    # back truncated, the ratio reads low, and the row is flagged "suspect
    # under-logging" — manufacturing the exact artifact SKILL.md warns is the
    # biggest source of false optimism here. It biases the weighted ratio
    # hardest, since the tickets with the most entries are the largest ones.
    cmd = ["rmine", "time", "list", "--issue", issue_id, "--all", "-o", "json"]
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
    """Gather {issue_id: hours} from files and directories."""
    return {issue_id: hours for issue_id, (hours, _) in collect_records(paths).items()}


def collect_records(paths):
    """Gather {issue_id: (hours, mode)} from files and directories.

    A ticket estimated in more than one file keeps the last one read, in the
    sorted order below — which is filename order, not date order.
    """
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
        for issue_id, hours, mode in parse_estimate_records(path):
            seen[issue_id] = (hours, mode)
    return seen


def plural(n, noun):
    return f"{n} {noun}" + ("" if n == 1 else "s")


def well_below(ratio, group_median):
    """Whether a ticket sits so far under the rest that its logging is suspect."""
    return ratio < LOW_VS_REST * group_median


def summarize(rows):
    """Aggregate drift for one group of tickets, all priced in the same mode.

    `consistent` counts tickets within ±25% of the group's own median: whether
    there is a pattern at all. `accurate` counts tickets within ±25% of 1.0:
    whether the estimates were right. A team that steadily overestimates is
    consistent and not accurate, which is exactly the drift worth correcting.
    """
    ratios = sorted(r["ratio"] for r in rows)
    mid = median(ratios)
    estimated = sum(r["estimated"] for r in rows)
    actual = sum(r["actual"] for r in rows)
    return {
        "tickets": len(ratios),
        "estimated": estimated,
        "actual": actual,
        "weighted": actual / estimated,
        "median": mid,
        "low": ratios[0],
        "high": ratios[-1],
        "consistent": sum(1 for x in ratios if 0.75 * mid <= x <= 1.25 * mid),
        "accurate": sum(1 for x in ratios if 0.75 <= x <= 1.25),
        "well_below_rest": sum(1 for x in ratios if well_below(x, mid)),
    }


def bar(s):
    """The conditions of SKILL.md's bar that a summary doesn't meet.

    An empty list means the numbers clear it. Whether the tickets flagged as
    well below the rest were really under-logged is for the developer to say,
    so it isn't decided here.
    """
    unmet = []
    if s["tickets"] < MIN_TICKETS:
        unmet.append(f"{plural(s['tickets'], 'ticket')}; the bar needs {MIN_TICKETS}+")
    if s["consistent"] * 2 <= s["tickets"]:
        unmet.append("half or fewer sit within ±25% of the median: no consistent pattern")
    if 0.75 <= s["median"] <= 1.25:
        unmet.append("the median is within ±25% of 1.0: nothing systematic to correct")
    if (s["weighted"] - 1) * (s["median"] - 1) < 0:
        unmet.append("weighted and median point different ways")
    return unmet


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", help="an estimates/ directory, individual estimate files, or one file holding many")
    ap.add_argument("--profile", help="rmine profile to use")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    estimates = collect_records(args.paths)
    if not estimates:
        sys.exit("no estimates found — expected a Redmine issue URL and a Total line")

    rows, missing = [], []
    for issue_id, (est, mode) in sorted(estimates.items(), key=lambda kv: int(kv[0])):
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
            "mode": mode or "unstated",
        })

    groups = {}
    for r in rows:
        groups.setdefault(r["mode"], []).append(r)
    summaries = {mode: summarize(group) for mode, group in groups.items()}
    for r in rows:
        r["well_below_rest"] = well_below(r["ratio"], summaries[r["mode"]]["median"])

    if args.json:
        print(json.dumps({
            "rows": rows,
            "missing": [{"issue": i, "estimated": e, "reason": r} for i, e, r in missing],
            "modes": {m: dict(s, unmet=bar(s)) for m, s in summaries.items()},
        }, indent=2))
        return

    print(f"{'issue':>7} {'est':>7} {'actual':>7} {'ratio':>6} {'who':>4} "
          f"{'mode':<13} {'status':<12} notes")
    for r in rows:
        notes = []
        if r["excluded"]:
            notes.append(f"excluded {r['excluded']:g}h non-work")
        if r["well_below_rest"]:
            notes.append("well below the rest: ask whether all time was logged")
        print(f"{r['issue']:>7} {r['estimated']:>7g} {r['actual']:>7.1f} "
              f"{r['ratio']:>6.2f} {r['loggers']:>4} {r['mode']:<13} {r['status']:<12} "
              f"{', '.join(notes)}")

    for issue_id, est, reason in missing:
        print(f"{issue_id:>7} {est:>7g} {'—':>7} {'—':>6} {'—':>4} {'—':<13} {'—':<12} {reason}")

    if not rows:
        sys.exit("\nno tickets had logged time — nothing to calibrate against")

    print(f"\ncovered          {len(rows)} of {len(estimates)} tickets"
          f" ({len(missing)} without usable logged time)")
    # Each mode prices from its own rubric column, so each gets its own numbers.
    for mode in sorted(summaries):
        s = summaries[mode]
        unmet = bar(s)
        print(f"\n{mode}: {plural(s['tickets'], 'ticket')}")
        print(f"  weighted ratio   {s['weighted']:.2f}  "
              f"({s['actual']:g}h actual / {s['estimated']:g}h estimated)")
        print(f"  median ratio     {s['median']:.2f}")
        print(f"  spread           {s['low']:.2f} – {s['high']:.2f}")
        print(f"  consistent       {s['consistent']} of {s['tickets']} within ±25% of the median")
        print(f"  accurate         {s['accurate']} of {s['tickets']} within ±25% of 1.0")
        print(f"  well below rest  {s['well_below_rest']}  (ask about these before trusting the bar)")
        print(f"  bar              {'met' if not unmet else 'not met: ' + '; '.join(unmet)}")
    print("\nThe weighted ratio is dominated by big tickets; the median is not.")
    print("When they disagree, the drift is not uniform — read the table, and")
    print("see SKILL.md before changing any anchor.")


if __name__ == "__main__":
    main()
