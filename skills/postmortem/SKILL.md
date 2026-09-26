---
name: postmortem
description: Compare one finished ticket's estimate, line by line, against where the time actually went — which lines ran over or under, and which rubric anchor rows look wrong — and write it up as the per-ticket evidence a rubric change needs. Use when the user asks how an estimate held up, why a ticket ran over, wants a postmortem or retro on an estimate, or needs evidence for changing a rubric anchor row.
---

# Postmortem

`/calibrate` works in aggregate, and it requires that any anchor change "name
the tickets in the PR description". This skill produces that per-ticket
evidence: for one finished ticket, which estimate lines were priced from which
anchor row, how much time actually went into each, and which rows the result
argues against.

**Redmine records time per ticket per day, never per line.** So the per-line
split is reconstructed: the ticket branch's commits say which lines the
development time went into, and the developer who did the work confirms or
corrects it. The write-up marks every number as either measured from git or
judged by the developer. A postmortem that hides which is which is not
evidence.

## 0. Preflight

```sh
rmine whoami
```

You need the product repo with the ticket's committed
`estimates/estimate-<id>.md`, and the ticket branch available locally. No
estimate file means there is nothing to hold the work against; say so and
stop.

## 1. Only finished work

```sh
rmine issue view <id> -o json
```

Run on a ticket whose development is over: a closed status, or one whose name
says the work shipped (for example Deployed, Verified or QA Completed). Ask
when a status could mean either.
**An in-flight ticket makes every line look under**, and a rubric PR built on
it would lower anchors for no reason.

If the user wants it anyway, go ahead, but the write-up is marked `PARTIAL`
in its header and summary, and says it must not be cited in a rubric PR.

## 2. Line up the estimate against the branch

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/postmortem/scripts/attribute.py" \
  --estimate estimates/estimate-<id>.md --repo <product repo> --json
```

The script:

- parses the estimate's priced leaf lines, each with its section and any
  `Anchor:` row under it;
- takes the ticket branch's own commits (first-parent, merges excluded), keeps
  those by the people who logged time on the ticket and made after the
  estimate's `Date:`, and reports how many others it dropped;
- matches each changed file to the lines that name it (`Cdw::Mappers::UkRecordMapper`
  → `cdw/mappers/uk_record_mapper.rb`, a spec path to that spec);
- splits the logged **Development** hours across lines by each line's share of
  commit activity, in 0.25h steps that sum exactly to the Development total.

Other activities (Design, Peer Review, Testing) come back as their own totals,
along with every time entry's date, hours and comment.

## 3. Resolve what git couldn't

Ask the developer who did the work (the one who logged the Development time),
in one round:

- **Unmatched files.** Code rarely keeps the names an estimate used —
  `PcbRecordMerger` shipped as `UkRecordConsolidator`. For each unmatched file,
  which line it belongs to, or none (scope that wasn't in the estimate, which
  is itself a finding). Rerun with `--assign <file-or-glob>=<line>`.
- **Lines git can't see.** Demo, PR reviews and discussions make no commits.
  Use the non-Development activity totals and the time-entry comments
  ("Development completed and demo") to propose hours, and have the developer
  settle them.
- **Estimating time.** Time logged for reading the spec and writing the
  estimate is not work the estimate priced. Keep it out of the line
  comparison and report it on its own.

## 4. Confirm the split

Show one table: line, section, anchor, estimated, proposed actual, and whether
the number is `measured` (git share, unchanged) or `judged` (set or changed by
the developer). Ask the developer to confirm it with AskUserQuestion; any line
they change becomes `judged`. The per-line actuals must add up to the logged
work time, less estimating time; if they don't, say where the difference is.

## 5. Read the anchors

For each line with an `Anchor:` row, compare the confirmed actual against the
**anchor's range**, not just the line's estimate:

- inside the range: the row held, whatever the line's estimate was;
- outside it: the row looks wrong for this kind of work, and the line is
  evidence against it;
- lines with no anchor are judgment calls, and say nothing about the rubric.

**One ticket is one data point.** Never recommend changing a row from a single
postmortem. Say what would make it evidence: the same row outside its range
across several postmortems, linked together in a rubric PR as `/calibrate`
requires.

## 6. Write it up

Write `postmortems/postmortem-<id>.md` in the product repo, next to `estimates/`
and **never inside it**: `/calibrate` reads every file in `estimates/`, and a
postmortem there would be counted as a second estimate for the ticket.

```
Task: <subject>
Redmine: <url>
Estimate: estimates/estimate-<id>.md (<estimate date>, by <estimator>)
Postmortem: <today>, confirmed by <developer>
Status: <status>   [PARTIAL: ticket still in progress; not for rubric PRs]

Summary: estimated <E> hrs, logged <L> hrs of work (<activities>), plus <S> hrs estimating.

Lines:
| # | Line | Anchor | Est | Actual | Basis |

Anchor rows:
- <row> (<range>): actual <A> — inside / outside the range

Scope not in the estimate: <files or work, with hours>

Method: <N> commits on <branch> since <date> by <authors>; <M> dropped.
Assigned by the developer: <file → line>.
```

Tell the user to commit it. A postmortem that isn't committed can't be linked
from the rubric PR it exists to support.
