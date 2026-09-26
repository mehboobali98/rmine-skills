---
name: log
description: Draft a day's Redmine time entries from git activity, get them approved, and log them with rmine. Use when the user asks to log time, fill in or backfill their hours or timesheet, says they forgot to log time, or asks what they worked on for a given day.
---

# Log

`/calibrate` can only measure what people logged, and it names unlogged hours
as the single biggest source of false optimism in its analysis. This skill is
the fix for that: it reads what git already knows about the day, turns it into
drafted `rmine time log` calls, and logs them once the user approves.

**Git does not know how long anyone worked.** It knows which tickets were
touched and roughly when. So the user gives the day's total and this skill
splits it; it never invents hours on its own.

**This skill writes to Redmine, and never without explicit approval** — the
same rule as `/spec-interview` §6, restated in step 8 because it applies here
in full.

## 0. Preflight

```sh
rmine whoami
rmine version
```

`whoami` covers a missing binary, no profile and bad credentials. The preview
in step 7 needs `--dry-run`, added in rmine v0.9.0; if `rmine version` is
older, stop and point at
`go install github.com/mehboobali98/rmine/cmd/rmine@latest`.

## 1. Which day

Default to today. Accept "yesterday", a weekday name, or a date, and resolve it
to `YYYY-MM-DD` before going further. Refuse a future date.

For several days (a backfill), run the whole skill once per day, oldest first,
with its own total and its own approval. A single approval covering a week of
entries is too much to check.

## 2. What's already logged

```sh
rmine time list --user me --from <day> --to <day> -o json
```

Show it. Then ask for the day's total hours worked, **including** anything
already logged, and work out what is left:

    remaining = total - already logged

If nothing remains, say the day is fully logged and stop.

## 3. Collect git activity

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/log/scripts/activity.py" \
  --date <day> --root <work folder> --exclude <personal folder> --json
```

`--root` is the folder holding the user's work repos and worktrees. Ask once
if it isn't obvious from the working directory. Exclude personal and side
projects: their branch names can carry numbers that look like ticket IDs, and
the script cannot tell the difference.

The script replays each worktree's reflog, attributes every commit, checkout,
rebase and reset to the branch it happened on, and groups the day's events by
the ticket ID in the branch or folder name (`feature/55365_...`,
`ezofficeinventory-55726-kandji-sync`). A PR review worktree
(`...-pr39587-review`) is resolved to its PR's branch with `gh`, and logged as
Peer Review. Each entry comes back with its minutes, time span and commit
subjects. Events that hit three or more worktrees within seconds are dropped as
tool activity.

## 4. Ask about what git can't see

In one question, not one per item:

- **Branches with no ticket** (the `unattributed` list): for each, which ticket
  it was for, or drop it. Pass the answers back as
  `--map <branch>=<ticket>`.
- **Work git never saw:** design, meetings, reviews done in the browser,
  support. Take a ticket and hours for each. These hours are the user's, so
  they are logged exactly as given and are not part of the split.

If a ticket the script found already has time logged that day, leave it out
of the split unless the user says the logged entry was for something else.
Double-logging is the error this step exists to prevent.

## 5. Split the rest

    git hours = remaining - hours the user gave in step 4

Rerun the script with `--total <git hours>` (and any `--map`). The split is in
proportion to each ticket's minutes, in 0.5h steps, and always sums to exactly
the total. A ticket that rounds to 0h is listed so the user can raise it or
drop it; don't silently discard it.

## 6. Check the tickets, and draft

For each ticket:

```sh
rmine issue view <id> -o json
```

A ticket that doesn't exist or looks wrong for the work (a folder reused for
something else) goes back to the user. A closed ticket can still take time;
mention it, don't block on it.

Draft a table, one row per entry:

| Ticket | Subject | Activity | Hours | Comment | Evidence |
|---|---|---|---|---|---|

- **Activity** is the script's guess: Development for feature and hotfix work,
  Peer Review for review worktrees, Design for doc and architecture work. The
  user corrects it here.
- **Comment** is one plain line built from the commit subjects, at most about
  80 characters. Leave it empty rather than invent one for a ticket with no
  commits.
- **Evidence** is the span and a count of events, so the user can tell a real
  session from a stray checkout.

## 7. Preview

For each row:

```sh
rmine time log <id> --date <day> --hours <h> --activity "<activity>" \
  --comment "<comment>" --dry-run -o json
```

This resolves the activity name and every ticket exactly as the real call
will, without logging anything. A rejection here (an unknown activity, a
ticket the user can't log to) is fixed before asking for approval, not after.
Keep comments free of `$`, backticks and double quotes, which the shell would
rewrite.

## 8. Approve, then log

**The `rmine time log` calls run only after the user has seen the final table
and approved it, in this run, for this day.** Logged time feeds `/calibrate`
and every report built on Redmine, and cleaning up a wrong entry is a manual
job for someone.

- **Ask with AskUserQuestion.** The yes must be a choice the user made, not an
  inference from silence or from the run having got this far.
- **"Log my time for today" authorises the run, not the entries.** They did
  not exist when it was said. Draft, show, then ask.
- **A yes does not carry.** Not to another day, and not to a changed table.
  Change a row and ask again.
- **If you cannot ask, you cannot log.** In a non-interactive run, print the
  table and the commands, and say plainly that nothing was logged and why.

Then run the same commands as step 7 without `--dry-run`, one at a time. If
one fails, stop and report which entries were logged and which were not;
don't retry blindly, because a retry after a timeout can log the same entry
twice.

## 9. Report

```sh
rmine time list --user me --from <day> --to <day>
```

Its total should now equal the total the user gave in step 2. If it doesn't,
say by how much and why, rather than calling the day done.
