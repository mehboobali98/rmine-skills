#!/usr/bin/env python3
"""Collect one day's git activity per Redmine ticket, and split a day's hours.

Walks every git worktree under the given roots, replays each one's HEAD reflog
to work out which branch every commit, checkout, rebase or reset landed on,
and groups the day's events by the ticket ID in the branch or folder name.

    activity.py --date 2026-09-25 --root ~/work
    activity.py --date 2026-09-25 --root ~/work --total 6.5 --json

Stdlib only; shells out to git, and to gh to find the branch behind a PR
review worktree.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

# Events on one ticket closer together than this are one working session.
SESSION_GAP_MIN = 45
# A session's first event is not when the work on it started.
SESSION_LEAD_MIN = 15
# One person cannot act in this many worktrees within a few seconds, so an
# event shared that widely came from a script or tool, not from work.
BULK_WORKTREES = 3
BULK_WINDOW_SEC = 5

TICKET_RE = re.compile(r"(?:^|[/_-])(\d{4,6})(?=[_-]|$)")
PR_RE = re.compile(r"(?:^|[/_-])pr(\d+)(?=[_-]|$)", re.I)
REVIEW_RE = re.compile(r"(?:^|[/_-])(?:review|verify)(?=[_-]|$)", re.I)
DESIGN_RE = re.compile(r"(?:^|[/_-])(?:doc|docs|arch|architecture|design|spec)(?=[_-]|$)", re.I)
REFLOG_RE = re.compile(r"^HEAD@\{(\d+)\}\t(.*)$")
CHECKOUT_RE = re.compile(r"^checkout: moving from (\S+) to (\S+)$")


def ticket_from(name):
    """The Redmine ticket ID in a branch or folder name, or None."""
    m = TICKET_RE.search(name or "")
    return int(m.group(1)) if m else None


def activity_for(branch, folder):
    """The Redmine activity a piece of work most likely was."""
    if PR_RE.search(folder) or REVIEW_RE.search(folder):
        return "Peer Review"
    if DESIGN_RE.search(folder) or DESIGN_RE.search(branch or ""):
        return "Design"
    return "Development"


def parse_reflog(lines):
    """(unix time, message) pairs from `git reflog --date=unix`, newest first."""
    out = []
    for line in lines:
        m = REFLOG_RE.match(line)
        if m:
            out.append((int(m.group(1)), m.group(2)))
    return out


def attribute(entries, current_branch):
    """(time, branch, message) for each reflog entry, newest first.

    Replays backwards from the branch checked out now: an entry belongs to the
    branch that was current when it was written, and a checkout entry is the
    point where, going back in time, the branch changes to the one it moved
    from.
    """
    out = []
    branch = current_branch
    for ts, msg in entries:
        m = CHECKOUT_RE.match(msg)
        if m:
            out.append((ts, m.group(2), msg))
            branch = m.group(1)
        else:
            out.append((ts, branch, msg))
    return out


def session_minutes(times):
    """Minutes of work implied by a set of event times, in seconds."""
    if not times:
        return 0
    times = sorted(times)
    total = SESSION_LEAD_MIN * 60
    for prev, cur in zip(times, times[1:]):
        gap = cur - prev
        total += gap if gap <= SESSION_GAP_MIN * 60 else SESSION_LEAD_MIN * 60
    return round(total / 60)


def split_hours(weights, total, step=0.5):
    """Share total hours across keys in proportion to weights, in whole steps.

    Largest remainder, so the parts always sum to exactly total. A key whose
    share rounds to nothing gets 0 and is the caller's to drop or raise.
    """
    units = round(total / step)
    whole = sum(weights.values())
    if units <= 0 or whole <= 0:
        return {k: 0.0 for k in weights}
    raw = {k: units * w / whole for k, w in weights.items()}
    parts = {k: int(v) for k, v in raw.items()}
    left = units - sum(parts.values())
    for k in sorted(raw, key=lambda k: (parts[k] - raw[k], k))[:left]:
        parts[k] += 1
    return {k: parts[k] * step for k in weights}


def git(path, *args):
    r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def find_worktrees(roots, excludes=(), depth=2):
    """Every worktree under roots, plus any worktree those repos link to
    elsewhere, minus anything under an excluded folder."""
    found = set()
    for root in roots:
        root = os.path.expanduser(root)
        base = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, _ in os.walk(root):
            if os.path.exists(os.path.join(dirpath, ".git")):
                found.add(os.path.realpath(dirpath))
            if dirpath.count(os.sep) - base >= depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
    for path in list(found):
        for line in git(path, "worktree", "list", "--porcelain").splitlines():
            if line.startswith("worktree "):
                wt = line[len("worktree "):]
                if os.path.isdir(wt):
                    found.add(os.path.realpath(wt))
    skip = [os.path.realpath(os.path.expanduser(e)) for e in excludes]
    return sorted(p for p in found if not any(p == s or p.startswith(s + os.sep) for s in skip))


def pr_branch(path, number):
    r = subprocess.run(["gh", "pr", "view", str(number), "--json", "headRefName", "-q", ".headRefName"],
                       cwd=path, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def day_window(day):
    start = time.mktime(day.timetuple())
    end = time.mktime((day + timedelta(days=1)).timetuple())
    return start, end


def drop_bulk(per_worktree):
    """Remove events that fired in BULK_WORKTREES or more worktrees within
    BULK_WINDOW_SEC of each other."""
    stamps = sorted((e[0], wt) for wt, events in per_worktree.items() for e in events)

    def spread(ts):
        return len({wt for t, wt in stamps if abs(t - ts) <= BULK_WINDOW_SEC})

    return {wt: [e for e in events if spread(e[0]) < BULK_WORKTREES] for wt, events in per_worktree.items()}


def collect(worktrees, day, lookup_pr=pr_branch, mapping=None):
    """Group a day's reflog events by (ticket, activity), or by branch when no
    ticket. mapping assigns a ticket to branches whose names carry none."""
    mapping = mapping or {}
    start, end = day_window(day)
    per_worktree = {}
    for wt in worktrees:
        current = git(wt, "symbolic-ref", "-q", "--short", "HEAD").strip() or "(detached)"
        entries = parse_reflog(git(wt, "reflog", "show", "--date=unix", "--format=%gd%x09%gs", "HEAD").splitlines())
        per_worktree[wt] = [e for e in attribute(entries, current) if start <= e[0] < end]

    groups = {}
    for wt, todays in drop_bulk(per_worktree).items():
        if not todays:
            continue
        folder = os.path.basename(wt)
        pr = PR_RE.search(folder)
        review_branch = lookup_pr(wt, int(pr.group(1))) if pr else None
        for ts, branch, msg in todays:
            ticket = ticket_from(review_branch) if pr else ticket_from(branch) or mapping.get(branch) or ticket_from(folder)
            activity = activity_for(branch, folder)
            if ticket:
                key = ("ticket", ticket, activity)
            else:
                key = ("unattributed", folder, "PR #%s" % pr.group(1) if pr else branch)
            g = groups.setdefault(key, {"times": [], "where": set(), "commits": []})
            g["times"].append(ts)
            g["where"].add("%s (%s)" % (folder, branch))
            if msg.startswith("commit") and ": " in msg:
                subject = msg.split(": ", 1)[1]
                if subject not in g["commits"]:
                    g["commits"].append(subject)
    return groups


def report(groups, total=None, step=0.5):
    def span(times):
        fmt = lambda t: datetime.fromtimestamp(t).strftime("%H:%M")
        return "%s-%s" % (fmt(min(times)), fmt(max(times)))

    entries, unattributed = [], []
    for key, g in groups.items():
        row = {
            "minutes": session_minutes(g["times"]),
            "events": len(g["times"]),
            "span": span(g["times"]),
            "where": sorted(g["where"]),
            "commits": g["commits"],
        }
        if key[0] == "ticket":
            entries.append({"ticket": key[1], "activity": key[2], **row})
        else:
            unattributed.append({"folder": key[1], "branch": key[2], **row})

    if total is not None:
        shares = split_hours({(e["ticket"], e["activity"]): e["minutes"] for e in entries}, total, step)
        for e in entries:
            e["hours"] = shares[(e["ticket"], e["activity"])]
    entries.sort(key=lambda e: -e["minutes"])
    unattributed.sort(key=lambda u: -u["minutes"])
    return {"entries": entries, "unattributed": unattributed}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--date", default=date.today().isoformat(), help="day to collect, YYYY-MM-DD (default today)")
    ap.add_argument("--root", action="append", required=True, help="folder holding git repos (repeatable)")
    ap.add_argument("--exclude", action="append", default=[], help="folder to skip, e.g. personal repos (repeatable)")
    ap.add_argument("--map", action="append", default=[], metavar="BRANCH=TICKET",
                    help="count a branch with no ticket in its name toward a ticket (repeatable)")
    ap.add_argument("--total", type=float, help="hours to split across the tickets found")
    ap.add_argument("--step", type=float, default=0.5, help="hour granularity of the split (default 0.5)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args(argv)

    day = datetime.strptime(args.date, "%Y-%m-%d").date()
    mapping = {}
    for pair in args.map:
        branch, _, ticket = pair.rpartition("=")
        if not branch or not ticket.isdigit():
            ap.error("--map takes BRANCH=TICKET, got %r" % pair)
        mapping[branch] = int(ticket)
    worktrees = find_worktrees(args.root, args.exclude)
    result = report(collect(worktrees, day, mapping=mapping), args.total, args.step)
    result["date"] = args.date

    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    for e in result["entries"]:
        hours = "  %4.1fh" % e["hours"] if "hours" in e else ""
        print("#%-6d %-12s %4d min %s%s  %s" % (e["ticket"], e["activity"], e["minutes"], e["span"], hours, ", ".join(e["where"])))
    for u in result["unattributed"]:
        print("(no ticket) %-40s %4d min %s  %s" % (u["branch"], u["minutes"], u["span"], u["folder"]))
    if not result["entries"] and not result["unattributed"]:
        print("No git activity found on %s." % args.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
