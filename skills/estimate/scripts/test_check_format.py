#!/usr/bin/env python3
"""Tests for check_format.py.

The checker gates step 5 of /estimate and the validator agent reports its
output verbatim, so a checker that silently stops catching things is worse
than no checker. Run with: python3 test_check_format.py

Stdlib only, no test runner needed.
"""
import os
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_format import check  # noqa: E402

GOOD = """\
Task: Allow exporting widgets from the listing screen
Redmine: https://redmine.example.com/issues/12345
Estimated by: A. Engineer
Date: 2026-03-04
Confidence: High — every line item priced from a matching anchor row
Assumptions:
  AI-assisted development.
Breakdown:
Backend (2.5 hrs)
  Export service following the existing CSV exporter pattern (2 hr)
    Column selection from the list view preference
  Controller action, route, ability (0.5 hr)
Frontend (N/A)
Testing (0.5 hr)
Demo + PR Reviews (2 hrs)
Discussions + Additional cases: 3 hours
  Retention policy was never specified
Total (8 hrs ~ 2 points)
"""

# (name, mutation applied to GOOD, substring expected in some problem)
CASES = [
    ("clean", lambda s: s, None),
    ("bad points",
     lambda s: s.replace("~ 2 points", "~ 3 points"), "points should be"),
    ("section sum wrong",
     lambda s: s.replace("Backend (2.5 hrs)", "Backend (3 hrs)"), "line items sum to"),
    ("total wrong",
     lambda s: s.replace("Total (8 hrs", "Total (9 hrs"), "sections sum to"),
    ("trailing commentary",
     lambda s: s + "\nHappy to break this down further.\n", "last line must be"),
    ("assumptions below breakdown",
     lambda s: s.replace("Assumptions:\n  AI-assisted development.\n", "")
                .replace("Breakdown:", "Breakdown:\nAssumptions:"), "must sit above"),
    ("missing header",
     lambda s: s.replace("Date: 2026-03-04\n", ""), "missing `Date:`"),
    ("bare confidence",
     lambda s: s.replace("Confidence: High — every line item priced from a matching anchor row",
                         "Confidence: High"), "needs a reason"),
    ("bad confidence grade",
     lambda s: s.replace("Confidence: High —", "Confidence: Certain —"), "must be High, Medium or Low"),
    ("non-iso date",
     lambda s: s.replace("Date: 2026-03-04", "Date: 4 March 2026"), "ISO"),
    ("off-grid granularity",
     lambda s: s.replace("(2 hr)\n", "(2.1 hr)\n").replace("Backend (2.5 hrs)", "Backend (2.6 hrs)")
                .replace("Total (8 hrs", "Total (8.1 hrs"), "0.25 hr granularity"),
    ("priced sub-detail",
     lambda s: s.replace("    Column selection from the list view preference",
                         "    Column selection from the list view preference (1 hr)"),
     "don't carry their own"),
    ("unnamed discussion buffer",
     lambda s: s.replace("  Retention policy was never specified\n", ""), "they're padding"),
    ("missing frontend layer",
     lambda s: s.replace("Frontend (N/A)\n", ""), "no Frontend section"),
    ("N/A section with line items",
     lambda s: s.replace("Frontend (N/A)", "Frontend (N/A)\n  Something (1 hr)"), "N/A but has line items"),
]


def run():
    failures = []
    for name, mutate, expected in CASES:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(mutate(GOOD))
            path = f.name
        try:
            problems = check(path)
        finally:
            os.unlink(path)

        if expected is None:
            if problems:
                failures.append(f"{name}: expected no problems, got {problems}")
        elif not any(expected in p for p in problems):
            failures.append(f"{name}: expected a problem containing {expected!r}, got {problems or 'none'}")

    for failure in failures:
        print("FAIL " + failure)
    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
