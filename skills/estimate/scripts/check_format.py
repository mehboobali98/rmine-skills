#!/usr/bin/env python3
"""Validate an estimate against the house format in references/rubric.md.

Everything checked here is arithmetic or shape — deterministic, and cheaper to
catch with a script than with a reviewer's attention. `Total (Z hrs ~ P points)`
is parsed downstream by calibrate/scripts/actuals.py, so an estimate that
drifts from the format silently drops out of the calibration corpus.

    check_format.py estimates/estimate-54039.md
    check_format.py estimates/

Exit 0 when every file passes, 1 otherwise. Stdlib only.
"""
import argparse
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

NUM = r"\d+(?:\.\d+)?"

# "Backend (4 hrs)", "Frontend (N/A)", "Demo + PR Reviews + Testing (2 hr)"
SECTION_RE = re.compile(r"^(?P<name>\S.*?)\s+\((?P<value>N/A|" + NUM + r"\s*(?:hrs?|hours?))\)\s*$")
# "Discussions + Additional cases: 2 hours" — colon form, no parentheses
DISCUSSION_RE = re.compile(r"^Discussions \+ Additional cases:\s*(?P<hours>" + NUM + r")\s*(?:hrs?|hours?)\s*$")
# A priced line item ends in "(2 hr)"; sub-details must not.
PRICED_RE = re.compile(r"\((?P<hours>" + NUM + r")\s*(?:hrs?|hours?)\)\s*$")
CONFIDENCE_RE = re.compile(r"^Confidence:\s*(High|Medium|Low)\b\s*(?P<why>.*)$")
DATE_RE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})\s*$")
TOTAL_RE = re.compile(
    r"^Total \((?P<hours>" + NUM + r")\s*(?:hrs?|hours?)(?:\s*~\s*(?P<points>\d+)\s*(?:points?|pts?))?\)\s*$"
)


def hours_of(value):
    """Pull the number out of '4 hrs' / '0.5 hr'. None for N/A."""
    if value.strip().upper() == "N/A":
        return None
    return float(re.match(NUM, value.strip()).group(0))


def expected_points(hours):
    """round(hours / 4), half away from zero — not Python's banker's rounding."""
    return int((Decimal(str(hours)) / 4).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def off_grid(hours):
    """True when hours isn't a multiple of the 0.25 granularity the rubric sets."""
    return (Decimal(str(hours)) * 4) % 1 != 0


def check(path):
    """Return a list of problem strings for one estimate file."""
    problems = []
    with open(path) as f:
        lines = [line.rstrip("\n") for line in f]

    def flag(i, msg):
        problems.append(f"{path}:{i + 1}: {msg}")

    body = [(i, line) for i, line in enumerate(lines) if line.strip()]
    if not body:
        return [f"{path}: empty file"]

    # --- the parsed contract: Total is the literal last line -----------------
    last_i, last_line = body[-1]
    total_match = TOTAL_RE.match(last_line)
    if not total_match:
        flag(last_i, f"last line must be `Total (Z hrs ~ P points)`, got: {last_line!r}")
        return problems  # nothing below depends on a total we couldn't read

    total_hours = float(total_match.group("hours"))
    points = total_match.group("points")
    if points is None:
        if total_hours >= 4:
            flag(last_i, f"points are only droppable below ~4 hrs, and this is {total_hours}")
    else:
        want = expected_points(total_hours)
        if int(points) != want:
            flag(last_i, f"points should be round({total_hours}/4) = {want}, got {points}")

    # --- provenance header ---------------------------------------------------
    # Who and when make per-person drift readable in /calibrate and make a
    # stale estimate visible. Confidence is what stops a point number being
    # read as more certain than the spec it came from.
    header = {}
    for i, line in enumerate(lines):
        key, sep, _ = line.partition(":")
        if sep and not line.startswith(" "):
            header.setdefault(key.strip(), i)

    for required in ("Task", "Redmine", "Estimated by", "Date", "Confidence"):
        if required not in header:
            problems.append(f"{path}: missing `{required}:` header line")

    if "Date" in header:
        i = header["Date"]
        if not DATE_RE.match(lines[i]):
            flag(i, "Date must be ISO `YYYY-MM-DD`")
    if "Confidence" in header:
        i = header["Confidence"]
        confidence = CONFIDENCE_RE.match(lines[i])
        if not confidence:
            flag(i, "Confidence must be High, Medium or Low")
        elif not confidence.group("why").strip(" -\u2014"):
            flag(i, "Confidence needs a reason after it — a bare grade says nothing")

    # --- Assumptions above Breakdown, so the total stays last ----------------
    heads = {line.strip(): i for i, line in enumerate(lines) if line.strip() in ("Assumptions:", "Breakdown:")}
    if "Breakdown:" not in heads:
        problems.append(f"{path}: no `Breakdown:` line")
        return problems
    if "Assumptions:" not in heads:
        flag(heads["Breakdown:"], "no `Assumptions:` block — it is required, above `Breakdown:`")
    elif heads["Assumptions:"] > heads["Breakdown:"]:
        flag(heads["Assumptions:"], "`Assumptions:` must sit above `Breakdown:`")

    # --- sections, line items, sub-details -----------------------------------
    sections = []       # (line_no, name, declared_hours or None for N/A)
    items = []          # list per section, of (line_no, hours)
    gaps = []           # named gaps under the Discussions line
    in_discussion = False
    seen_total = False

    for i, line in enumerate(lines):
        if i <= heads["Breakdown:"] or not line.strip():
            continue
        if TOTAL_RE.match(line):
            seen_total = True
            continue
        if seen_total:
            flag(i, "nothing may follow the Total line — downstream tooling parses it as last")
            continue

        indent = len(line) - len(line.lstrip())

        if indent == 0:
            discussion = DISCUSSION_RE.match(line)
            if discussion:
                sections.append((i, "Discussions + Additional cases", float(discussion.group("hours"))))
                items.append([])
                in_discussion = True
                continue
            section = SECTION_RE.match(line)
            if section:
                sections.append((i, section.group("name"), hours_of(section.group("value"))))
                items.append([])
                in_discussion = False
                continue
            flag(i, f"unindented line is neither a section heading nor the Total: {line.strip()!r}")
        elif indent == 2 and in_discussion:
            # "Name the gaps, or drop the line" — these are gap names, and
            # hours here would mean the buffer was subdivided into line items.
            if PRICED_RE.search(line):
                flag(i, "a named gap under Discussions carries no hours of its own")
            else:
                gaps.append(i)
        elif indent == 2:
            priced = PRICED_RE.search(line)
            if not priced:
                flag(i, f"line item carries no hours: {line.strip()!r}")
            elif not sections:
                flag(i, "line item appears before any section heading")
            else:
                items[-1].append((i, float(priced.group("hours"))))
        else:
            if PRICED_RE.search(line):
                flag(i, "sub-details justify a line item's hours, they don't carry their own")

    if not sections:
        problems.append(f"{path}: no sections found under `Breakdown:`")
        return problems

    # --- arithmetic ----------------------------------------------------------
    for (i, name, declared), section_items in zip(sections, items):
        if declared is None:            # N/A: considered, nothing needed
            if section_items:
                flag(i, f"{name} is N/A but has line items under it")
            continue
        if off_grid(declared):
            flag(i, f"{name} ({declared}) is not a multiple of the 0.25 hr granularity")
        for item_i, item_hours in section_items:
            if off_grid(item_hours):
                flag(item_i, f"{item_hours} is not a multiple of the 0.25 hr granularity")
        if section_items:
            summed = sum(h for _, h in section_items)
            if abs(summed - declared) > 1e-9:
                flag(i, f"{name} declares {declared} but its line items sum to {summed:g}")

    # The Discussions buffer is where acknowledged uncertainty gets priced. An
    # unnamed buffer is padding, which the rubric refuses.
    if any(name.startswith("Discussions") for _, name, _ in sections) and not gaps:
        discussion_line = next(i for i, name, _ in sections if name.startswith("Discussions"))
        flag(discussion_line, "name the gaps these hours buy, or drop the line — unnamed, they're padding")

    summed_sections = sum(d for _, _, d in sections if d is not None)
    if abs(summed_sections - total_hours) > 1e-9:
        flag(last_i, f"Total is {total_hours} but the sections sum to {summed_sections:g}")

    # --- the layers must be accounted for, not omitted -----------------------
    named = " ".join(name for _, name, _ in sections).lower()
    for layer in ("backend", "frontend"):
        if layer not in named.replace("-", ""):
            problems.append(f"{path}: no {layer.title()} section — an untouched layer gets `N/A`, not omission")

    return problems


def collect(paths):
    for path in paths:
        if os.path.isdir(path):
            for entry in sorted(os.listdir(path)):
                if entry.endswith(".md"):
                    yield os.path.join(path, entry)
        else:
            yield path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+", help="estimate files, or a directory of them")
    args = ap.parse_args()

    files = list(collect(args.paths))
    if not files:
        print("no .md files found", file=sys.stderr)
        return 1

    failed = 0
    for path in files:
        problems = check(path)
        if problems:
            failed += 1
            for problem in problems:
                print(problem)
        else:
            print(f"{path}: ok")

    if failed:
        print(f"\n{failed} of {len(files)} file(s) failed the format contract", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
