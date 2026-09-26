#!/usr/bin/env python3
"""Line up one ticket's estimate against what its branch and its time log show.

Parses the estimate's priced line items (with any `Anchor:` row under each),
matches the files the ticket branch changed to the items that name them, and
proposes how the logged Development hours split across the items by each
one's share of the branch's commit activity. It is a proposal: the skill has
the developer confirm or correct it before anything is written.

    attribute.py --estimate estimates/estimate-55238.md --repo . \\
        --branch feature/55238_cdw_uk_pcb_record_correlation --json
    attribute.py ... --assign app/services/cdw/uk_record_consolidator.rb=3

Stdlib only. Reuses /estimate's outline parser and /calibrate's time totals.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "estimate", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "calibrate", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "log", "scripts"))
import activity  # noqa: E402
import actuals  # noqa: E402
import check_format as fmt  # noqa: E402

SESSION_GAP_MIN = 45
SESSION_LEAD_MIN = 15
BACKTICK_RE = re.compile(r"`([^`]+)`")
ANCHOR_RE = re.compile(r"^Anchor:\s*(?P<row>.*)$")
IDENT_RE = re.compile(r"^[A-Za-z0-9_:./-]+$")
BASES = ("origin/develop", "develop", "origin/main", "main", "origin/master", "master")


def snake(name):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def hints_from(text):
    """Path hints for the files a line of estimate text names.

    `Cdw::Mappers::UkRecordMapper#map` becomes cdw/mappers/uk_record_mapper,
    a path stays a path, and anything that isn't an identifier or a path
    (`record['Asset_Tag']`, prose) is ignored.
    """
    hints = []
    for token in BACKTICK_RE.findall(text):
        token = re.split(r"[#(]", token.strip())[0]
        if not IDENT_RE.match(token) or len(token) < 5:
            continue
        if "::" in token:
            hints.append("/".join(snake(p) for p in token.split("::")))
        elif "/" in token or "." in token:
            hints.append(token.lower())
        elif token[0].isupper():
            hints.append(snake(token))
    return sorted(set(hints))


def file_matches(path, hint):
    """Whether a changed file is the one a hint names."""
    path = path.lower()
    stem = os.path.splitext(path)[0]
    if "." in os.path.basename(hint):
        return path == hint or path.endswith("/" + hint)
    return stem == hint or stem.endswith("/" + hint)


def parse_items(path):
    """Priced leaf items of the estimate's Breakdown, in order.

    A priced line with priced lines under it is a subtotal, not an item. A
    section priced on its own line with nothing priced under it (Demo + PR
    Reviews, Discussions) is an item itself.
    """
    lines = open(path).read().splitlines()
    start = next((i for i, l in enumerate(lines) if fmt.content(l).replace("*", "").strip() == "Breakdown:"), None)
    if start is None:
        raise ValueError("%s has no Breakdown: line" % path)
    levels = fmt.levels_of(lines, start)

    rows = []
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        text = fmt.content(line)
        if fmt.TOTAL_RE.match(text):
            break
        level = levels[len(line) - len(line.lstrip())]
        priced = fmt.PRICED_RE.search(text)
        section = fmt.SECTION_RE.match(text) if level == 0 else None
        discussion = fmt.DISCUSSION_RE.match(text) if level == 0 else None
        hours = None
        if discussion:
            hours = float(discussion.group("hours"))
        elif priced:
            hours = float(priced.group("hours"))
        rows.append({"level": level, "text": text, "hours": hours, "section": bool(section or discussion)})

    items, current_section = [], None
    for n, row in enumerate(rows):
        if row["level"] == 0:
            current_section = re.sub(r"\s*[:(].*$", "", row["text"])
        if row["hours"] is None:
            continue
        below = []
        for later in rows[n + 1:]:
            if later["level"] <= row["level"]:
                break
            below.append(later)
        if any(b["hours"] is not None for b in below):
            continue
        anchor = next((ANCHOR_RE.match(b["text"]).group("row") for b in below if ANCHOR_RE.match(b["text"])), None)
        items.append({
            "n": len(items) + 1,
            "section": current_section,
            "text": fmt.PRICED_RE.sub("", row["text"]).strip(),
            "estimate": row["hours"],
            "anchor": anchor,
            "hints": hints_from(" ".join([row["text"]] + [b["text"] for b in below])),
        })
    return items


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "git %s failed" % args[0])
    return r.stdout


def find_base(repo, branch):
    for candidate in BASES:
        try:
            return candidate, git(repo, "merge-base", candidate, branch).strip()
        except RuntimeError:
            continue
    raise RuntimeError("no develop, main or master to measure %s against" % branch)


def branch_commits(repo, branch, base_sha):
    """(author time, author, [files]) for the branch's own commits, oldest first.

    --first-parent keeps out whatever was merged into the branch: a ticket
    branch that merged a long-lived branch in reaches thousands of commits
    that were not this ticket's work.
    """
    out = git(repo, "log", "--first-parent", "--no-merges", "--reverse", "--format=\x01%at\t%an", "--name-only",
              "%s..%s" % (base_sha, branch))
    commits = []
    for chunk in out.split("\x01")[1:]:
        lines = [l for l in chunk.splitlines() if l.strip()]
        when, _, author = lines[0].partition("\t")
        commits.append((int(when), author, lines[1:]))
    return commits


def ticket_work(commits, authors, since):
    """The commits that are this ticket's work, and how many were dropped.

    A merge-base is not enough on its own: a branch can still reach older
    commits by other people that the base branch no longer has as ancestors.
    Keep commits by the people who logged time on the ticket, made after it
    was estimated.
    """
    wanted = {a.lower() for a in authors}
    kept = [c for c in commits if (not wanted or c[1].lower() in wanted) and (since is None or c[0] >= since)]
    return kept, len(commits) - len(kept)


def estimate_date(path):
    for line in open(path):
        m = fmt.DATE_RE.match(fmt.content(line).replace("*", ""))
        if m:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
    return None


def commit_weights(times):
    """Minutes each commit stands for: the gap since the previous one within a
    session, or the lead-in when it opens a session."""
    weights, prev = [], None
    for t in times:
        gap = None if prev is None else (t - prev) / 60
        weights.append(gap if gap is not None and gap <= SESSION_GAP_MIN else SESSION_LEAD_MIN)
        prev = t
    return weights


def attribute(items, commits, assign=None):
    """Share of the branch's commit activity per item, plus unmatched files."""
    assign = assign or {}
    minutes = {it["n"]: 0.0 for it in items}
    unmatched = {}
    for weight, (_, _, files) in zip(commit_weights([c[0] for c in commits]), commits):
        if not files:
            continue
        per_file = weight / len(files)
        for f in files:
            owners = [n for pattern, n in assign.items() if fnmatch.fnmatch(f, pattern)]
            if not owners:
                owners = [it["n"] for it in items if any(file_matches(f, h) for h in it["hints"])]
            if owners:
                for n in owners:
                    minutes[n] += per_file / len(owners)
            else:
                unmatched[f] = unmatched.get(f, 0.0) + per_file
    total = sum(minutes.values()) + sum(unmatched.values())
    share = {n: (m / total if total else 0.0) for n, m in minutes.items()}
    unmatched_share = {f: m / total for f, m in unmatched.items()} if total else {}
    return share, unmatched_share


def logged(ticket, profile=None):
    cmd = ["rmine", "time", "list", "--issue", str(ticket), "--all", "-o", "json"]
    if profile:
        cmd += ["--profile", profile]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "rmine exited %d" % proc.returncode)
    entries = json.loads(proc.stdout or "[]") or []
    by_activity, work = {}, []
    for e in entries:
        activity = (e.get("activity") or {}).get("name", "?")
        if activity.strip().lower() in actuals.NON_WORK_ACTIVITIES:
            continue
        by_activity[activity] = by_activity.get(activity, 0.0) + float(e.get("hours") or 0)
        work.append({"date": e.get("spent_on"), "hours": e.get("hours"), "activity": activity,
                     "user": (e.get("user") or {}).get("name"), "comment": e.get("comments") or ""})
    return by_activity, sorted(work, key=lambda w: w["date"] or "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--estimate", required=True, help="the ticket's estimate-<id>.md")
    ap.add_argument("--repo", required=True, help="the product repo holding the ticket branch")
    ap.add_argument("--branch", help="the ticket branch (default: the one local branch naming the ticket)")
    ap.add_argument("--assign", action="append", default=[], metavar="FILE_OR_GLOB=N",
                    help="count a changed file toward item N (repeatable)")
    ap.add_argument("--author", action="append", default=[],
                    help="git author whose commits count (repeatable; default: whoever logged time on the ticket)")
    ap.add_argument("--profile")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    ticket = next((int(i) for i, _ in actuals.parse_estimates(args.estimate)), None)
    if ticket is None:
        ap.error("no Redmine ticket found in %s" % args.estimate)
    items = parse_items(args.estimate)

    branch = args.branch
    if not branch:
        found = [b.strip("* ").strip() for b in git(args.repo, "branch", "--list", "*%d*" % ticket).splitlines()]
        if len(found) != 1:
            ap.error("pass --branch: %d local branches name #%d (%s)" % (len(found), ticket, ", ".join(found) or "none"))
        branch = found[0]
    assign = {}
    for pair in args.assign:
        pattern, _, n = pair.rpartition("=")
        if not pattern or not n.isdigit() or int(n) not in {it["n"] for it in items}:
            ap.error("--assign takes FILE_OR_GLOB=N with N an item number, got %r" % pair)
        assign[pattern] = int(n)

    by_activity, entries = logged(ticket, args.profile)
    authors = args.author or sorted({e["user"] for e in entries if e["user"]})
    estimated_on = estimate_date(args.estimate)
    since = (estimated_on - timedelta(days=1)).timestamp() if estimated_on else None

    base_name, base_sha = find_base(args.repo, branch)
    commits, dropped = ticket_work(branch_commits(args.repo, branch, base_sha), authors, since)
    share, unmatched = attribute(items, commits, assign)
    dev = by_activity.get("Development", 0.0)
    weights = {("item", n): s for n, s in share.items()}
    weights.update({("file", f): s for f, s in unmatched.items()})
    proposed = activity.split_hours(weights, dev, step=0.25)
    for it in items:
        it["share"] = round(share[it["n"]], 3)
        it["proposed"] = proposed[("item", it["n"])]

    result = {
        "ticket": ticket,
        "estimate_total": sum(it["estimate"] for it in items),
        "items": items,
        "logged": {"total": sum(by_activity.values()), "by_activity": by_activity, "entries": entries},
        "git": {"branch": branch, "base": base_name, "commits": len(commits), "dropped": dropped,
                "authors": authors, "since": estimated_on.date().isoformat() if estimated_on else None,
                "unmatched": [{"file": f, "share": round(s, 3), "proposed": proposed[("file", f)]}
                              for f, s in sorted(unmatched.items(), key=lambda kv: -kv[1])]},
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print("#%d: estimated %.2fh, logged %.2fh (%s)" % (ticket, result["estimate_total"], result["logged"]["total"],
          ", ".join("%s %.2fh" % kv for kv in sorted(by_activity.items()))))
    print("%s against %s: %d commits by %s since the estimate (%d others dropped)\n"
          % (branch, base_name, len(commits), ", ".join(authors) or "anyone", dropped))
    print("%3s  %-16s %6s %8s %6s  %s" % ("N", "SECTION", "EST", "PROPOSED", "SHARE", "ITEM"))
    for it in items:
        print("%3d  %-16s %5.2fh %7.2fh %5d%%  %s%s" % (it["n"], (it["section"] or "")[:16], it["estimate"], it["proposed"],
              round(it["share"] * 100), it["text"][:70], "  [anchor: %s]" % it["anchor"][:40] if it["anchor"] else ""))
    if unmatched:
        print("\nfiles no item names (assign with --assign FILE=N):")
        for u in result["git"]["unmatched"]:
            print("  %5d%%  %s" % (round(u["share"] * 100), u["file"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
