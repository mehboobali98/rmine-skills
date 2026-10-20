#!/usr/bin/env python3
"""Tests for rollup.py.

The roll-up is what a rubric PR quotes as evidence that an anchor row is
wrong, so a row it mismatches or a postmortem it miscounts becomes a wrong
anchor for the whole team. Run with: python3 test_rollup.py

Stdlib only, no test runner needed.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rollup  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


RUBRIC = """\
## Calibration anchors

| Work | Hand-written | Agent-driven | Basis |
|---|---|---|---|
| Controller + routes + ability + CRUD actions | 2–4 | 0.5–1 | measured once (#8) |
| Model only (associations, validations) | 0.25–1 | 0.25–1 | held (#8) |
| Global / elastic search integration | ~4 | 1–2 | judgment |
| Sync / integration logic against a third-party API | 4+ | 2+ | judgment |
"""


def postmortem(issue, anchors, mode="agent-driven", status="Closed"):
    mode_line = f"Mode: estimated agent-driven, work done {mode}\n" if mode else ""
    lines = "".join(f"- {row} ({rng}): actual {actual} — inside / outside the range\n"
                    for row, rng, actual in anchors)
    return (
        f"Task: Ticket {issue}\n"
        f"Redmine: https://redmine.example.com/issues/{issue}\n"
        f"Estimate: estimates/estimate-{issue}.md (2026-10-01, by A. Engineer)\n"
        f"Postmortem: 2026-10-15, confirmed by A. Engineer\n"
        f"Status: {status}\n"
        f"{mode_line}"
        f"\nSummary: estimated 10 hrs, logged 6 hrs of work.\n"
        f"\nLines:\n| # | Line | Anchor | Est | Actual | Basis |\n"
        f"\nAnchor rows ({mode or 'unstated'} column):\n{lines}"
        f"\nScope not in the estimate: none\n"
    )


CONTROLLER = "Controller + routes + ability + CRUD actions"
MODEL = "Model only (associations, validations)"
SEARCH = "Global / elastic search integration"

POSTMORTEMS = {
    "postmortem-201.md": postmortem(201, [(CONTROLLER, "0.5–1", 1.5), (MODEL, "0.25–1", 0.5),
                                          (SEARCH, "1–2", 0.75)]),
    "postmortem-202.md": postmortem(202, [(CONTROLLER, "0.5–1", 2), (SEARCH, "1–2", 1.5)]),
    "postmortem-203.md": postmortem(203, [(CONTROLLER, "0.5–1", 1.75)]),
    # In flight: every line looks under, and SKILL.md says never to cite it.
    "postmortem-204.md": postmortem(204, [(CONTROLLER, "0.5–1", 0.1)],
                                    status="In Progress   [PARTIAL: ticket still in progress; not for rubric PRs]"),
    # Written before /postmortem recorded the mode.
    "postmortem-205.md": postmortem(205, [(CONTROLLER, "2–4", 0.5)], mode=None),
    "postmortem-206.md": postmortem(206, [(CONTROLLER, "2–4", 3)], mode="hand-written"),
    "postmortem-207.md": postmortem(207, [("Bulk import wizard (FE)", "~3", 2)]),
}


def run_rollup():
    tmp = tempfile.mkdtemp()
    try:
        rubric_path = os.path.join(tmp, "rubric.md")
        with open(rubric_path, "w") as f:
            f.write(RUBRIC)
        folder = os.path.join(tmp, "postmortems")
        os.mkdir(folder)
        for name, text in POSTMORTEMS.items():
            with open(os.path.join(folder, name), "w") as f:
                f.write(text)
        return rollup.rollup(rollup.collect([folder]), rollup.parse_rubric(rubric_path), min_evidence=3)
    finally:
        shutil.rmtree(tmp)


def row(result, name, mode):
    found = [r for r in result["rows"] if r["row"] == name and r["mode"] == mode]
    return found[0] if found else None


def test_parses_ranges():
    cases = [
        ("0.5–1", (0.5, 1.0)), ("0.25-0.5", (0.25, 0.5)), ("~4", (3.0, 5.0)),
        ("4+", (4.0, float("inf"))), ("0.25", (0.25, 0.25)), ("about a day", None),
    ]
    for text, want in cases:
        check(f"parse_range({text!r})", rollup.parse_range(text), want)


# A row whose name carries its own parentheses must not lose them to the
# range that follows.
def test_parses_a_row_with_parentheses_in_its_name():
    check("anchor line", rollup.parse_anchor_line(f"- {MODEL} (0.25–1): actual 0.5 — inside the range"),
          (MODEL, 0.5))


def test_a_row_outside_its_range_across_three_postmortems_is_a_candidate():
    r = row(run_rollup(), CONTROLLER, "agent-driven")
    check("evidence", r["evidence"], [("201", 1.5), ("202", 2.0), ("203", 1.75)])
    check("all above", (r["below"], r["inside"], r["above"]), (0, 0, 3))
    check("median", r["median"], 1.75)
    check("candidate", r["candidate"], True)


def test_a_row_split_across_its_range_is_not_a_candidate():
    r = row(run_rollup(), SEARCH, "agent-driven")
    check("split", (r["below"], r["inside"], r["above"]), (1, 1, 0))
    check("not a candidate", r["candidate"], False)
    check("judgment basis carried", r["basis"], "judgment")


def test_reads_each_postmortem_against_the_column_for_its_mode():
    r = row(run_rollup(), CONTROLLER, "hand-written")
    check("hand-written column", r["range"], "2–4")
    check("inside", (r["below"], r["inside"], r["above"]), (0, 1, 0))


def test_partial_postmortems_are_never_counted():
    result = run_rollup()
    check("skipped", result["skipped"], ["204"])
    check("not in the evidence", any(issue == "204" for issue, _ in row(result, CONTROLLER, "agent-driven")["evidence"]),
          False)


def test_unstated_mode_is_reported_without_a_verdict():
    r = row(run_rollup(), CONTROLLER, "unstated")
    check("evidence kept", r["evidence"], [("205", 0.5)])
    check("no range to judge against", r["range"], None)
    check("no candidate", r["candidate"], False)


def test_rows_the_rubric_doesnt_have_are_listed_not_dropped():
    check("unmatched", run_rollup()["unmatched"], [("207", "Bulk import wizard (FE)", 2.0)])


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    if FAILURES:
        print("FAIL")
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)
    print("ok — rollup.py")


if __name__ == "__main__":
    main()
