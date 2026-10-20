#!/usr/bin/env python3
"""Roll every postmortem up into one view per rubric anchor row.

One postmortem is one data point, and SKILL.md never lets it move a row. A
rubric PR needs the same row across several finished tickets, and gathering
that by hand means reopening every write-up. This reads the `Anchor rows`
section of each postmortem, groups the actual hours by row and by the mode the
work used, and sets them against that mode's column in the rubric as it is
today.

    rollup.py postmortems/
    rollup.py postmortems/ --min 3 --json

Stdlib only.
"""
import argparse
import json
import os
import re
import sys
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUBRIC = os.path.join(HERE, "..", "..", "estimate", "references", "rubric.md")

NUM = r"\d+(?:\.\d+)?"
ISSUE_RE = re.compile(r"/issues/(\d+)")
# "Mode: estimated agent-driven, work done hand-written" — the work's mode is
# the one that matters, since that is the column the actual hours speak to.
MODE_RE = re.compile(r"work done\s+(agent-driven|hand-written)", re.I)
# "- Model only (associations, validations) (0.25–1): actual 0.5 — inside".
# The row is matched lazily up to the last parenthesised range before the
# colon, so a row name with its own parentheses survives intact.
ANCHOR_LINE_RE = re.compile(
    r"^[-*]\s+(?P<row>.+?)\s+\((?P<range>[^()]*)\)\s*:\s*actual\s+(?P<actual>" + NUM + r")"
)
COLUMNS = ("hand-written", "agent-driven")


def parse_range(text):
    """(low, high) for an anchor range: `0.5–1`, `~4` (±25%), `4+`, `0.25`."""
    text = text.strip()
    m = re.fullmatch(r"(" + NUM + r")\s*(?:–|-|to)\s*(" + NUM + r")", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.fullmatch(r"~\s*(" + NUM + r")", text)
    if m:
        about = float(m.group(1))
        return about * 0.75, about * 1.25
    m = re.fullmatch(r"(" + NUM + r")\s*\+", text)
    if m:
        return float(m.group(1)), float("inf")
    m = re.fullmatch(NUM, text)
    if m:
        return float(text), float(text)
    return None


def normalize(name):
    return re.sub(r"\s+", " ", name.replace("`", "").replace("*", "")).strip().lower()


def parse_rubric(path):
    """{normalized row name: {"name", "hand-written", "agent-driven", "basis"}}."""
    rows = {}
    header = None
    with open(path) as f:
        for line in f:
            if not line.lstrip().startswith("|"):
                header = None if rows else header
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if header is None:
                if [c.lower() for c in cells[:3]] == ["work", "hand-written", "agent-driven"]:
                    header = [c.lower() for c in cells]
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            record = dict(zip(header, cells))
            rows[normalize(record["work"])] = {
                "name": record["work"],
                "hand-written": record.get("hand-written"),
                "agent-driven": record.get("agent-driven"),
                "basis": record.get("basis", ""),
            }
    return rows


def parse_anchor_line(line):
    """(row, actual hours) from one `Anchor rows` line, or None."""
    m = ANCHOR_LINE_RE.match(line.strip())
    if not m:
        return None
    return m.group("row").strip().strip("`*"), float(m.group("actual"))


def parse_postmortem(path):
    """The issue, whether it is PARTIAL, the work's mode, and its anchor rows."""
    issue, partial, mode, anchors = None, False, None, []
    in_anchors = False
    with open(path) as f:
        for line in f:
            text = line.strip()
            if issue is None and text.lower().startswith("redmine:"):
                found = ISSUE_RE.search(text)
                issue = found.group(1) if found else None
            if text.lower().startswith("status:") and "PARTIAL" in text:
                partial = True
            if text.lower().startswith("mode:"):
                found = MODE_RE.search(text)
                mode = found.group(1).lower() if found else None
            if text.lower().startswith("anchor rows"):
                in_anchors = True
                continue
            if in_anchors:
                if not text:
                    continue
                parsed = parse_anchor_line(text)
                if parsed is None:
                    in_anchors = False
                    continue
                anchors.append(parsed)
    if issue is None:
        found = re.search(r"(\d+)", os.path.basename(path))
        issue = found.group(1) if found else os.path.basename(path)
    return {"issue": issue, "partial": partial, "mode": mode, "anchors": anchors}


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(os.path.join(p, n) for n in os.listdir(p) if n.endswith(".md"))
        else:
            files.append(p)
    return [parse_postmortem(path) for path in files]


def match(name, rubric):
    """The rubric row a postmortem's row name refers to, or None."""
    key = normalize(name)
    if key in rubric:
        return rubric[key]
    close = [row for k, row in rubric.items() if k.startswith(key) or key.startswith(k)]
    return close[0] if len(close) == 1 else None


def rollup(postmortems, rubric, min_evidence=3):
    """Group actual hours by (row, mode) and judge them against today's rubric.

    A row is a candidate for a rubric PR when at least `min_evidence`
    postmortems put it outside its range, all on the same side. Postmortems
    with no recorded mode are listed but never judged: there is no telling
    which column their hours speak to.
    """
    groups, skipped, unmatched = {}, [], []
    for pm in postmortems:
        if pm["partial"]:
            skipped.append(pm["issue"])
            continue
        mode = pm["mode"] or "unstated"
        for name, actual in pm["anchors"]:
            found = match(name, rubric)
            if found is None:
                unmatched.append((pm["issue"], name, actual))
                continue
            groups.setdefault((found["name"], mode), (found, []))[1].append((pm["issue"], actual))

    rows = []
    for (name, mode), (found, evidence) in sorted(groups.items()):
        rng = found.get(mode) if mode in COLUMNS else None
        bounds = parse_range(rng) if rng else None
        below = inside = above = 0
        if bounds:
            low, high = bounds
            for _, actual in evidence:
                if actual < low:
                    below += 1
                elif actual > high:
                    above += 1
                else:
                    inside += 1
        n = len(evidence)
        rows.append({
            "row": name, "mode": mode, "range": rng, "basis": found["basis"],
            "evidence": evidence, "median": median(a for _, a in evidence),
            "below": below, "inside": inside, "above": above,
            "candidate": bool(bounds) and n >= min_evidence and (below == n or above == n),
        })
    return {"rows": rows, "skipped": skipped, "unmatched": unmatched}


def report(result, counted, min_evidence):
    print(f"Anchor rows across {counted} postmortem(s)"
          + (f"; PARTIAL, not counted: {', '.join('#' + i for i in result['skipped'])}"
             if result["skipped"] else ""))
    for r in result["rows"]:
        actuals = ", ".join(f"#{issue} {actual:g}" for issue, actual in r["evidence"])
        print(f"\n{r['row']}")
        if r["range"] is None:
            print(f"  mode unstated: {actuals}")
            print("  add `Mode: estimated <mode>, work done <mode>` to these postmortems to judge them")
            continue
        # Basis describes the agent-driven figures only; the hand-written
        # column came from past estimates, as the rubric's Known bias says.
        agent = r["mode"] == "agent-driven"
        print(f"  {r['mode']} column {r['range']}" + (f" ({r['basis']})" if agent else ""))
        print(f"  {actuals}; median {r['median']:g}; "
              f"{r['below']} below, {r['inside']} inside, {r['above']} above")
        if r["candidate"]:
            side = "below" if r["below"] else "above"
            print(f"  candidate for a rubric PR: every actual {side} the range; cite {actuals}")
        elif agent and r["basis"].startswith("judgment"):
            print(f"  first measurements of a judgment row; {min_evidence} on one side would make it a candidate")
    if result["unmatched"]:
        print("\nRows the rubric doesn't have (a missing anchor row, or a name that drifted):")
        for issue, name, actual in result["unmatched"]:
            print(f"  #{issue} {name}: actual {actual:g}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", help="a postmortems/ directory or postmortem files")
    ap.add_argument("--rubric", default=DEFAULT_RUBRIC, help="rubric.md to judge against")
    ap.add_argument("--min", type=int, default=3, dest="min_evidence",
                    help="postmortems on one side of a range before a row is a candidate (default 3)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    postmortems = collect(args.paths)
    if not postmortems:
        sys.exit("no postmortems found")
    result = rollup(postmortems, parse_rubric(args.rubric), args.min_evidence)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    report(result, len(postmortems) - len(result["skipped"]), args.min_evidence)


if __name__ == "__main__":
    main()
