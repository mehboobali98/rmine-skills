#!/usr/bin/env python3
"""Tests for attribute.py. Run with: python3 test_attribute.py

Stdlib only, no test runner needed. The git test builds a throwaway repo with
fixed commit dates; rmine is faked by replacing subprocess.run for its calls.
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attribute  # noqa: E402

FAILURES = []
REAL_RUN = subprocess.run


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


ESTIMATE = """Task: Merge PCB records
Redmine: https://pm.example.com/issues/7001
Estimated by: Jane
Date: 2026-09-03
Confidence: Medium — one novel service
Assumptions:
  None.
Breakdown:
1. Backend (5 hrs)
    a. Extend `Cdw::Mappers::UkRecordMapper#map` with new keys (1 hr)
        i. Keys come from `record['Asset_Tag']`
    b. Implement `Cdw::PcbRecordMerger` (4 hrs)
        Anchor: Sync / integration logic against a third-party API (4+)
2. Frontend (N/A)
3. Testing (1 hr)
    a. Add `spec/services/cdw/pcb_record_merger_spec.rb` (1 hr)
4. Demo + PR Reviews (1 hr)
5. Discussions + Additional cases: 0.5 hr
6. Total (7.5 hrs ~ 2 points)
"""


def test_hints_from():
    check("namespaced class", attribute.hints_from("`Cdw::Mappers::UkRecordMapper#map`"), ["cdw/mappers/uk_record_mapper"])
    check("path", attribute.hints_from("`spec/services/cdw/x_spec.rb`"), ["spec/services/cdw/x_spec.rb"])
    check("tsx file", attribute.hints_from("`deviceNode.tsx`"), ["devicenode.tsx"])
    check("expression ignored", attribute.hints_from("`record['Asset_Tag']`"), [])
    check("plain snake word ignored", attribute.hints_from("`po_number`"), [])


def test_file_matches():
    check("class to file", attribute.file_matches("app/services/cdw/mappers/uk_record_mapper.rb", "cdw/mappers/uk_record_mapper"), True)
    check("class is not its spec", attribute.file_matches("spec/services/cdw/mappers/uk_record_mapper_spec.rb", "cdw/mappers/uk_record_mapper"), False)
    check("partial name is no match", attribute.file_matches("app/services/cdw/pcb_record_merger_v2.rb", "cdw/pcb_record_merger"), False)


def test_parse_items():
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(ESTIMATE)
    try:
        items = attribute.parse_items(f.name)
    finally:
        os.unlink(f.name)
    check("leaf items only", [(i["section"], i["estimate"]) for i in items],
          [("Backend", 1.0), ("Backend", 4.0), ("Testing", 1.0), ("Demo + PR Reviews", 1.0),
           ("Discussions + Additional cases", 0.5)])
    check("anchor captured", items[1]["anchor"], "Sync / integration logic against a third-party API (4+)")
    check("no anchor", items[0]["anchor"], None)
    check("hints from item and details", items[1]["hints"], ["cdw/pcb_record_merger"])


def test_commit_weights():
    check("session gaps", attribute.commit_weights([0, 600, 1200, 1200 + 7200]), [15, 10, 10, 15])


def test_ticket_work():
    commits = [(100, "Jane", ["a"]), (200, "Saqib", ["config"]), (50, "Jane", ["old"])]
    kept, dropped = attribute.ticket_work(commits, ["jane"], 80)
    check("other authors and older work dropped", (kept, dropped), ([(100, "Jane", ["a"])], 2))


def git(cwd, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Jane", GIT_AUTHOR_EMAIL="j@x", GIT_COMMITTER_NAME="Jane",
               GIT_COMMITTER_EMAIL="j@x")
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    REAL_RUN(["git", "-C", cwd, *args], check=True, capture_output=True, env=env)


def write(repo, path, text):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "a") as f:
        f.write(text)


def fake_rmine(cmd, **kwargs):
    if cmd[0] != "rmine":
        return REAL_RUN(cmd, **kwargs)
    entries = [
        {"spent_on": "2026-09-04", "hours": 2, "activity": {"name": "Design"}, "user": {"name": "Jane"}, "comments": "spec"},
        {"spent_on": "2026-09-05", "hours": 4, "activity": {"name": "Development"}, "user": {"name": "Jane"}, "comments": ""},
        {"spent_on": "2026-09-06", "hours": 8, "activity": {"name": "Leave"}, "user": {"name": "Jane"}, "comments": ""},
    ]
    return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(entries), stderr="")


def test_end_to_end():
    with tempfile.TemporaryDirectory() as root:
        repo = os.path.join(root, "app")
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "develop")
        write(repo, "README", "x")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "base", when="2026-08-01T09:00:00Z")
        git(repo, "checkout", "-q", "-b", "feature/7001_pcb")
        steps = [
            ("app/services/cdw/mappers/uk_record_mapper.rb", "2026-09-05T09:00:00Z"),
            ("app/services/cdw/uk_record_consolidator.rb", "2026-09-05T09:30:00Z"),
            ("spec/services/cdw/pcb_record_merger_spec.rb", "2026-09-05T10:00:00Z"),
        ]
        for path, when in steps:
            write(repo, path, "x")
            git(repo, "add", ".")
            git(repo, "commit", "-q", "-m", path, when=when)

        estimate = os.path.join(root, "estimate-7001.md")
        with open(estimate, "w") as f:
            f.write(ESTIMATE)

        out_path = os.path.join(root, "out.json")
        subprocess.run = fake_rmine
        try:
            with open(out_path, "w") as out:
                stdout, sys.stdout = sys.stdout, out
                try:
                    attribute.main(["--estimate", estimate, "--repo", repo, "--json",
                                    "--assign", "app/services/cdw/uk_record_consolidator.rb=2"])
                finally:
                    sys.stdout = stdout
        finally:
            subprocess.run = REAL_RUN
        result = json.load(open(out_path))

    check("ticket from the estimate", result["ticket"], 7001)
    check("branch found by ticket", result["git"]["branch"], "feature/7001_pcb")
    check("leave is not work", result["logged"]["by_activity"], {"Design": 2.0, "Development": 4.0})
    proposed = [i["proposed"] for i in result["items"]]
    check("development hours fully split", sum(proposed) + sum(u["proposed"] for u in result["git"]["unmatched"]), 4.0)
    check("assigned file counts toward its item", proposed[1] > 0, True)
    check("nothing left unmatched", result["git"]["unmatched"], [])
    check("non-code sections get nothing from git", proposed[3:], [0.0, 0.0])


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    if FAILURES:
        print("FAILED — attribute.py")
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)
    print("ok — attribute.py")


if __name__ == "__main__":
    main()
