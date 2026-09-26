---
name: sprint-plan
description: Check whether a sprint or monthly bucket fits the team — remaining estimated work per assignee against each person's capacity, with the tickets nobody has estimated called out rather than guessed. Use when the user asks if a sprint is overbooked, who has too much on, whether the team can finish a version or bucket, or wants capacity planning for a Redmine target version.
---

# Sprint plan

`/calibrate` says its weighted ratio "is what a sprint's capacity planning
cares about", and nothing did capacity planning. This skill does: it takes a
Redmine target version (a sprint, or a monthly bucket), works out each
assignee's remaining estimated work, and sets it against the hours they
actually have in the period.

**It is read-only.** It never reassigns, re-versions or re-estimates a
ticket. What to move is a conversation for the team; this skill supplies the
numbers for it.

**A team total hides the problem this exists to find.** A version can sit
comfortably under team capacity while several people on it are at double
theirs. Always lead with the per-person view.

## 0. Preflight

```sh
rmine whoami
```

Filtering by version needs rmine v0.6.0 or later.

## 1. Which version, and which period

Take a version name or ID and a project. If the user names neither, list the
open versions with `rmine project versions <project>`; for monthly buckets the
current month's is the usual answer.

The period is when the work has to be done. Default to today until the end of
the month (or the version's due date, if it has one), and say which dates you
used. Planning the rest of a month on its last Friday is a real question, so
don't silently widen it.

## 2. Capacity

Capacity is working days in the period, minus each person's leave, times hours
per day. Ask once, in one question, for what the numbers can't know:

- **Hours per day** a person spends on ticket work. The default is 8; after
  meetings and reviews it is often nearer 6, and that alone can flip a verdict.
- **Weekend days** (default Saturday and Sunday) and **public holidays** in
  the period.
- **Leave:** who is off, and for how many working days. Use the names exactly
  as Redmine shows them; the script lists any leave name it didn't match.
- **Anyone only partly on this version.** The script assumes everyone assigned
  here works only on it. Express part-time as leave days (half-time for 10 days
  is 5 days' leave) and say you did.

## 3. Run it

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/sprint-plan/scripts/plan.py" \
  --project <project> --version "<version>" --estimates <repo>/estimates \
  --from <start> --until <end> --hours-per-day <h> \
  --leave "<Name>=<days>" --holiday <YYYY-MM-DD> --json
```

Pass `--estimates` whenever the product repo has a committed `estimates/`
folder. For each open ticket the script takes the `/estimate` file's Total if
there is one, and Redmine's Estimated time otherwise, and flags the ticket when
the two differ by more than 25%. It subtracts the time already logged, leaving
out leave booked against the ticket (the same rule `/calibrate` uses), to get
what remains.

## 4. Read it before reporting it

- **`over`** means remaining estimated work already exceeds capacity, before
  counting anything unestimated. That is a firm finding.
- **`unknown, N unestimated`** means the person has tickets with no estimate,
  so their real load can't be known. Never fill the gap with a guess or an
  average: an invented number in a capacity plan reads as a measured one.
  List the tickets instead; getting them estimated (with `/estimate`, or
  in Redmine) is the action.
- **`tight`** is above 85%, with no room for the unplanned work every sprint
  has.
- **`no one to do it`** is unassigned work. It needs an owner before it can be
  planned at all.
- **Overruns** (time logged exceeds the estimate) count as 0 remaining, which
  is almost always wrong — the ticket is still open. Treat each one as
  unestimated work and say so; the estimate needs revisiting.
- **Disagreements** between an `/estimate` file and Redmine's field mean one
  of them is stale. The plan used the file; name the tickets so someone fixes
  the other.

## 5. Drift

Only adjust for estimation drift if `/calibrate`'s own bar is met on the
current corpus: run its script, and check for 20+ tickets, more than half
within ±25%, few under-logging flags, and weighted and median pointing the
same way.

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/calibrate/scripts/actuals.py" <repo>/estimates
```

If the bar isn't met, report unadjusted numbers and say plainly why, e.g.
*"the estimate corpus has 6 tickets; /calibrate needs 20 before its drift
means anything."* That sentence is part of the report, not a footnote.

If it is met, the adjustment is **one extra line**: the team's remaining work
from `/estimate` files, multiplied by the weighted ratio. It never touches
estimates that came from Redmine's field, because the drift was measured on
`/estimate` output and says nothing about how Redmine's numbers were made.
Never rewrite a per-ticket estimate with it — `/calibrate` forbids blanket
multipliers for good reason.

## 6. Report

Lead with the people who are over, then unknown, then tight, each with their
remaining hours, capacity and the tickets that make up the load. Then the team
line, the unassigned tickets, overruns, disagreements, and the drift sentence
from step 5.

End with what would change the picture, as suggestions for the user to act on:
tickets to estimate, overruns to re-estimate, work that could move from an
`over` person to an `ok` one. Name tickets, not categories.
