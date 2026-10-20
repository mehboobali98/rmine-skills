#!/usr/bin/env python3
"""Tests for actuals.py.

This script produces the numbers /calibrate reasons about, and a wrong number
here is worse than no number: it looks like evidence. Run with:
python3 test_actuals.py

Stdlib only, no test runner needed.
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actuals  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


class FakeRun:
    """Stands in for subprocess.run, recording the command and replaying JSON."""

    def __init__(self, payload):
        self.payload = payload
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 0, stdout=json.dumps(self.payload), stderr=""
        )


def entries(n, hours=1.0, activity="Development", user="Jane"):
    return [
        {
            "id": i,
            "hours": hours,
            "activity": {"name": activity},
            "user": {"name": user},
        }
        for i in range(n)
    ]


def with_fake_rmine(payload, fn):
    fake = FakeRun(payload)
    original = actuals.subprocess.run
    actuals.subprocess.run = fake
    try:
        return fn(), fake
    finally:
        actuals.subprocess.run = original


# `rmine time list` returns 25 entries by default. A ticket that ran for weeks
# has more, and the missing ones read as time nobody logged — which is the one
# artifact SKILL.md says poisons this analysis.
def test_asks_for_every_time_entry():
    (result, fake) = with_fake_rmine(entries(30), lambda: actuals.logged_hours("1234"))
    cmd = fake.commands[0]
    check("passes --all", "--all" in cmd, True)
    work, _, _ = result
    check("counts all 30 entries", work, 30.0)


def test_separates_non_work_activities():
    payload = entries(3) + entries(2, activity="Leave")
    (result, _) = with_fake_rmine(payload, lambda: actuals.logged_hours("1234"))
    work, nonwork, _ = result
    check("work hours", work, 3.0)
    check("non-work hours", nonwork, 2.0)


def test_counts_distinct_loggers():
    payload = entries(2, user="Jane") + entries(3, user="Ahmed")
    (result, _) = with_fake_rmine(payload, lambda: actuals.logged_hours("1234"))
    check("distinct loggers", result[2], 2)


# rmine prints [] for an empty list, but older builds printed null; the script
# has to survive both rather than crash mid-corpus.
def test_survives_empty_and_null_output():
    for payload in ([], None):
        (result, _) = with_fake_rmine(payload, lambda: actuals.logged_hours("1234"))
        check(f"empty payload {payload!r}", result[0], 0.0)


def test_threads_the_profile_through():
    (_, fake) = with_fake_rmine([], lambda: actuals.logged_hours("1234", "work"))
    cmd = fake.commands[0]
    check("passes --profile", cmd[-2:], ["--profile", "work"])


# The Total line is hand-written and its shapes vary; these are the ones seen
# in real estimate files, plus the decoys that must not parse.
def test_parses_total_line_shapes():
    cases = [
        ("Total (16 hrs ~ 4 points)", 16.0),
        ("Total: 4.25 hrs", 4.25),
        ("Total ~ 11 hrs", 11.0),
        ("Total (26.5 / 4 ~ 7 pts)", 26.5),
        ("Total: 19 + 6 + 60 = 44 ~ 11 points", 44.0),
        ("Total 16 actions", None),
        ("Total 17 relationships", None),
        ("Backend (2 hrs)", None),
        # Google Docs numbers every outline level, Total included. Unstripped,
        # the marker matched nothing and the whole estimate left the corpus.
        ("    6. Total (16 hrs ~ 4 points)", 16.0),
        ("6) Total: 4.25 hrs", 4.25),
        ("- Total ~ 11 hrs", 11.0),
        ("a. Total 16 actions", None),
        ("2. Backend (4 hrs)", None),
    ]
    for line, want in cases:
        check(f"parse_total({line!r})", actuals.parse_total(line), want)


def test_parses_estimates_from_a_file():
    content = (
        "Redmine: https://redmine.example.com/issues/54039\n"
        "Total (16 hrs ~ 4 points)\n"
        "Redmine: https://redmine.example.com/issues/54040\n"
        "Total: 8 hrs\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        found = dict(actuals.parse_estimates(path))
    finally:
        os.unlink(path)
    check("two estimates parsed", found, {"54039": 16.0, "54040": 8.0})


# estimate/SKILL.md tells estimators to name the linked tickets they treated as
# shipped foundations or dependencies in `Assumptions:`, and the natural way to
# write one is a link. Before the `Redmine:` header took precedence, that link
# stole the Total: the estimated ticket vanished from the corpus as "no time
# logged", and the linked ticket was scored against an estimate never made for
# it — a fabricated ratio landing straight in the weighted aggregate.
def test_linked_ticket_never_steals_the_total():
    content = (
        "Task: Widget audit trail\n"
        "Redmine: https://redmine.example.com/issues/12346\n"
        "Assumptions:\n"
        "  History tab is https://redmine.example.com/issues/12350, priced there.\n"
        "Breakdown:\n"
        "Backend (5 hrs)\n"
        "Total (5 hrs ~ 1 points)\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        found = dict(actuals.parse_estimates(path))
    finally:
        os.unlink(path)
    check("header wins over a linked URL", found, {"12346": 5.0})


# Estimates predating the header carry a bare URL and nothing else. They still
# have to parse, or the older half of the corpus disappears.
def test_bare_url_still_claims_its_total():
    content = (
        "https://redmine.example.com/issues/54039\n"
        "Total (16 hrs ~ 4 points)\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        found = dict(actuals.parse_estimates(path))
    finally:
        os.unlink(path)
    check("bare url parsed", found, {"54039": 16.0})


# The shape the corpus is actually written in: a numbered outline out of a
# Google Doc, bold header keys, Total numbered as the last item.
def test_parses_a_numbered_outline_estimate():
    content = (
        "**Task**: IT Asset Accuracy enablement\n"
        "**Redmine**: https://redmine.example.com/issues/54039\n"
        "**Breakdown**:\n"
        "    1. Backend (4 hrs)\n"
        "        a. New KPIs handling in:\n"
        "            i. FixedAssetKpiLinksGenerator\n"
        "    2. Frontend (7 hrs)\n"
        "    3. Demo + PR Reviews (2 hr)\n"
        "    4. Testing (1 hr)\n"
        "    5. Discussions + Additional cases: 2 hours\n"
        "    6. Total (16 hrs ~ 4 points)\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        found = dict(actuals.parse_estimates(path))
    finally:
        os.unlink(path)
    check("numbered outline parsed", found, {"54039": 16.0})


def records_of(content):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        return list(actuals.parse_estimate_records(path))
    finally:
        os.unlink(path)


# Agent-driven and hand-written estimates of the same ticket can sit more than
# twice apart, so every estimate has to carry its mode into the analysis.
# Estimates from before 0.9.0 have no Mode: line and come back as None.
def test_reads_each_estimates_mode():
    found = records_of(
        "**Redmine**: https://redmine.example.com/issues/1\n"
        "**Mode**: agent-driven\n"
        "Total (6 hrs ~ 2 points)\n"
        "Redmine: https://redmine.example.com/issues/2\n"
        "Mode: hand-written\n"
        "Total (12 hrs ~ 3 points)\n"
        "Redmine: https://redmine.example.com/issues/3\n"
        "Total (8 hrs ~ 2 points)\n"
    )
    check("modes per estimate", found, [
        ("1", 6.0, "agent-driven"), ("2", 12.0, "hand-written"), ("3", 8.0, None)])


def rows_at(*ratios):
    return [{"estimated": 10.0, "actual": 10.0 * r, "ratio": r} for r in ratios]


# The bug from #9: a ticket was flagged as suspect under-logging whenever it
# came in under half its estimate. A team whose estimates run a steady 2x high
# had every ticket flagged, and none of them within ±25% of 1.0, so the one
# drift calibration exists to find always read as noise.
def test_a_steady_overestimate_is_consistent_not_noise():
    s = actuals.summarize(rows_at(0.40, 0.42, 0.45, 0.45, 0.48, 0.50))
    check("consistent around the median", s["consistent"], 6)
    check("none accurate", s["accurate"], 0)
    check("none flagged as well below the rest", s["well_below_rest"], 0)


def test_scattered_ratios_are_not_consistent():
    s = actuals.summarize(rows_at(0.05, 0.8, 1.0, 2.96))
    check("scatter is not consistent", s["consistent"] * 2 <= s["tickets"], True)


def test_flags_a_ticket_far_below_the_rest():
    s = actuals.summarize(rows_at(0.1, 0.9, 1.0, 1.1))
    check("one ticket well below the rest", s["well_below_rest"], 1)
    check("flagged per ticket", actuals.well_below(0.1, s["median"]), True)
    check("not flagged", actuals.well_below(0.9, s["median"]), False)


def test_bar_is_met_by_a_steady_drift():
    check("20 tickets steady at 0.45", actuals.bar(actuals.summarize(rows_at(*[0.45] * 20))), [])


def test_bar_reasons():
    accurate = actuals.bar(actuals.summarize(rows_at(*[1.0] * 20)))
    check("accurate estimates have nothing to correct",
          any("nothing systematic to correct" in r for r in accurate), True)
    thin = actuals.bar(actuals.summarize(rows_at(*[0.45] * 6)))
    check("six tickets are too few", any("needs 20+" in r for r in thin), True)
    scattered = actuals.bar(actuals.summarize(rows_at(*([0.2, 0.5, 1.4, 3.0] * 5))))
    check("scatter has no pattern", any("no consistent pattern" in r for r in scattered), True)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    if FAILURES:
        print("FAIL")
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)
    print("ok — actuals.py")


if __name__ == "__main__":
    main()
