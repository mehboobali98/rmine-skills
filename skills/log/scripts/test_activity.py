#!/usr/bin/env python3
"""Tests for activity.py. Run with: python3 test_activity.py

Stdlib only, no test runner needed. The git tests build throwaway repos with
fixed commit dates, and run in UTC so the day boundaries are the same
everywhere.
"""
import os
import subprocess
import sys
import tempfile
import time
from datetime import date

os.environ["TZ"] = "UTC"
time.tzset()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import activity  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_ticket_from():
    check("feature branch", activity.ticket_from("feature/55365_itam9_backend"), 55365)
    check("hotfix branch", activity.ticket_from("hotfix/45629_allow_special"), 45629)
    check("worktree folder", activity.ticket_from("ezofficeinventory-55726-kandji-sync"), 55726)
    check("bare id branch", activity.ticket_from("55907_minitest_testing_rule"), 55907)
    check("no ticket", activity.ticket_from("feature/rails_upgrade_final_prod"), None)
    check("p21 is not a ticket", activity.ticket_from("feature/staging_branch_p21"), None)
    check("sha is not a ticket", activity.ticket_from("fa1063effa4fbc854ce05bd563719001bbcdec0d"), None)


def test_activity_for():
    check("review worktree", activity.activity_for("(detached)", "ezo-pr39587-review"), "Peer Review")
    check("verify worktree", activity.activity_for("(detached)", "ezo-pr39369-verify"), "Peer Review")
    check("doc worktree", activity.activity_for("feature/55735_x", "ezo-55735-doc"), "Design")
    check("architecture branch", activity.activity_for("feature/55936_kandji_architecture", "ezo"), "Design")
    check("plain feature", activity.activity_for("feature/55726_kandji_sync", "ezofficeinventory"), "Development")


def test_attribute_replays_checkouts_backwards():
    entries = activity.parse_reflog([
        "HEAD@{300}\tcommit: third",
        "HEAD@{200}\tcheckout: moving from feature/1111_a to feature/2222_b",
        "HEAD@{100}\tcommit: first",
        "not a reflog line",
    ])
    got = [(ts, branch) for ts, branch, _ in activity.attribute(entries, "feature/2222_b")]
    check("attribution", got, [(300, "feature/2222_b"), (200, "feature/2222_b"), (100, "feature/1111_a")])


def test_session_minutes():
    check("single event", activity.session_minutes([0]), 15)
    check("one session", activity.session_minutes([0, 600, 1800]), 15 + 30)
    check("two sessions", activity.session_minutes([0, 600, 600 + 3 * 3600]), 15 + 10 + 15)


def test_split_hours():
    got = activity.split_hours({"a": 104, "b": 93, "c": 15}, 8)
    check("split sums to total", sum(got.values()), 8)
    check("split in half hours", all(v * 2 == int(v * 2) for v in got.values()), True)
    check("largest share first", got["a"] >= got["b"] >= got["c"], True)
    check("no weight", activity.split_hours({"a": 0}, 4), {"a": 0.0})


def test_drop_bulk():
    per = {
        "w1": [(100, "b", "checkout"), (500, "b", "commit")],
        "w2": [(102, "b", "checkout")],
        "w3": [(104, "b", "checkout")],
    }
    got = activity.drop_bulk(per)
    check("bulk dropped, own work kept", got, {"w1": [(500, "b", "commit")], "w2": [], "w3": []})


def git(cwd, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    if when:
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = when
    subprocess.run(["git", "-C", cwd, *args], check=True, capture_output=True, env=env)


def test_collect_from_real_repos():
    with tempfile.TemporaryDirectory() as root:
        repo = os.path.join(root, "app")
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "base", when="2026-09-24T09:00:00Z")
        git(repo, "checkout", "-q", "-b", "feature/1111_login", when="2026-09-25T09:00:00Z")
        git(repo, "commit", "-q", "--allow-empty", "-m", "Add login", when="2026-09-25T09:20:00Z")
        git(repo, "checkout", "-q", "-b", "feature/2222_docs_arch", when="2026-09-25T14:00:00Z")
        git(repo, "commit", "-q", "--allow-empty", "-m", "Sketch design", when="2026-09-25T14:30:00Z")
        git(repo, "checkout", "-q", "-b", "feature/rails_upgrade", when="2026-09-25T16:00:00Z")
        git(repo, "commit", "-q", "--allow-empty", "-m", "Bump", when="2026-09-26T10:00:00Z")

        review = os.path.join(root, "app-pr42-review")
        git(repo, "worktree", "add", "-q", "--detach", review, "main", when="2026-09-25T11:00:00Z")

        worktrees = activity.find_worktrees([root])
        check("finds both worktrees", sorted(os.path.basename(w) for w in worktrees), ["app", "app-pr42-review"])

        groups = activity.collect(worktrees, date(2026, 9, 25), lookup_pr=lambda path, n: "feature/3333_fix" if n == 42 else None)
        result = activity.report(groups, total=4)
        got = {(e["ticket"], e["activity"]): e["hours"] for e in result["entries"]}
        check("tickets and activities", sorted(got), [(1111, "Development"), (2222, "Design"), (3333, "Peer Review")])
        check("hours sum to total", sum(got.values()), 4)
        check("next day's commit ignored", [u["branch"] for u in result["unattributed"]], ["feature/rails_upgrade"])
        login = next(e for e in result["entries"] if e["ticket"] == 1111)
        check("commit subjects kept", login["commits"], ["Add login"])

        mapped = activity.report(activity.collect(worktrees, date(2026, 9, 25), lookup_pr=lambda p, n: None,
                                                  mapping={"feature/rails_upgrade": 1111}))
        check("mapped branch joins its ticket", [u["branch"] for u in mapped["unattributed"]], ["PR #42"])

        check("excluded folder skipped", activity.find_worktrees([root], excludes=[review]), [os.path.realpath(repo)])


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    if FAILURES:
        print("FAILED — activity.py")
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)
    print("ok — activity.py")


if __name__ == "__main__":
    main()
