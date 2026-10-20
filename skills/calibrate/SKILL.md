---
name: calibrate
description: Compare past effort estimates against hours actually logged in Redmine, to find out whether the estimation rubric is systematically optimistic or pessimistic. Use when the user asks how accurate their estimates are, wants to calibrate or tune the estimate rubric, asks about estimate vs actual, estimation drift, or whether a team consistently over- or under-estimates.
---

# Calibrate

`/estimate` prices against the anchor table in
`skills/estimate/references/rubric.md`, which was derived from past
**estimates** — so it reproduces how those were made, including any systematic
error. This skill is the only thing that can tell you whether they were any
good. Now that the rubric is shared, a correction here moves every estimate the
team produces, which raises the bar for making one.

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/calibrate/scripts/actuals.py" <path>...
```

Point it at the product repo's committed `estimates/` directory — that's the
corpus `/estimate` builds up, one file per ticket. It also accepts individual
`estimate-<id>.md` files, or any single file holding many estimates. It parses
each estimate's issue reference and `Total` line, pulls matching time entries
via `rmine time list`, and reports a ratio per ticket plus aggregates.

**If the directory is thin, stop there.** The bar below needs 20+ tickets, and
a corpus that small means the answer is "not yet" regardless of what the ratios
say. That is a finding worth reporting, not a failure.

The script does the arithmetic. **Interpreting it is the hard part, and doing it
wrong is worse than not running it** — a confidently wrong multiplier applied
across a team's estimates is a lot of damage from one bad inference.

## Read the data quality before reading the numbers

Logged time is not ground truth. It is what people remembered to type in. Check
all of these before drawing any conclusion:

- **Mode.** Every estimate since 0.9.0 says in `Mode:` which rubric column it
  was priced from, and the script reports each mode on its own: agent-driven
  and hand-written estimates of the same ticket can sit more than twice apart,
  so pooling them measures the mix, not the drift. Estimates from before 0.9.0
  report as `unstated`. They were priced from what is now the Hand-written
  column, with the old in-range AI discount, so never read them alongside
  agent-driven ones.
- **`consistent` count** — tickets within ±25% of their mode's median. This is
  the headline: whether there is a pattern at all. If most tickets don't sit
  near the median, there is noise, not drift. A median of 0.8 built from ratios
  of 0.05 and 2.96 is not "20% optimistic", it's an average of unrelated
  numbers.
- **`accurate` count** — tickets within ±25% of 1.0: whether the estimates
  were right. Consistent but not accurate is the case worth correcting: every
  ticket near 0.45 is a steady overestimate, not noise. Until 0.10.0 this count
  was the headline, and a steady overestimate could never clear the bar (#9).
- **`well below the rest` flags** (ratio under half the mode's median). A
  shipped ticket that took a fraction of what its neighbours took may not have
  taken a fraction of the time: someone logged elsewhere, or not at all. **Ask
  the developer** whether all the time was logged, with AskUserQuestion, before
  reading the bar. A ticket they confirm stays in as evidence; one they don't
  is set aside, and you say which. Measured against the median rather than
  against 1.0, so a team that steadily overestimates doesn't see every ticket
  flagged.
- **`no time logged` rows.** Tickets absent from the sample entirely. If these
  are a large share, logging is discretionary and the tickets that *do* have
  time are a self-selected group.
- **Status.** Only a finished ticket has complete hours. An in-flight ticket
  shows a low ratio for a boring reason.
- **`excluded ... non-work`.** Redmine lets leave and holiday be booked against
  an issue. The script drops those; a large excluded figure means the raw
  numbers anyone else quotes from Redmine are inflated.
- **Logger count (`who`).** Several people on one ticket is normal and fine —
  the estimate covers the task, not one person. But it means you cannot read
  one person's calibration off a multi-logger ticket.

## Weighted vs median

Both are reported because they answer different questions and often disagree.

- **Weighted** (total actual / total estimated) is what a sprint's capacity
  planning cares about (`/sprint-plan` uses it, once this bar is met), and is
  dominated by the largest tickets.
- **Median** is the typical ticket, and ignores size.

When they diverge, drift is not uniform — most likely small tickets and large
tickets behave differently. Say that, rather than picking whichever number
supports the change you were going to make.

## What to actually change

**Default to changing nothing.** The bar for touching
`skills/estimate/references/rubric.md` is high, and is judged per mode:

- more than half the tickets within ±25% of the median, **and**
- the median outside ±25% of 1.0 (inside it, there is nothing systematic to
  fix), **and**
- weighted and median pointing the same direction, **and**
- few tickets well below the rest, after asking about them, **and**
- enough tickets that a couple of outliers can't set the result — 20+.

The script prints a `bar` line per mode with the first four of these checked;
the under-logging question is yours to settle with the developer.

Only then is there a signal. Even then, prefer the specific fix to the global
one, in this order:

1. **Adjust the individual anchor rows** whose work type shows consistent
   drift across several tickets. `/calibrate` only sees whole tickets; the
   row-level view comes from the postmortems:

   ```sh
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/postmortem/scripts/rollup.py" <repo>/postmortems
   ```

   It lists each anchor row's actual hours across every postmortem, against
   the rubric column for the mode the work used. Name the tickets in the PR
   description — an anchor change without the evidence attached can't be
   reviewed or reverted with confidence later.
2. **Add a missing anchor row** when the drift concentrates on work the table
   doesn't cover. Estimates for work with no matching row are flagged in their
   `Assumptions:` block as the estimator's judgment rather than the team's
   calibration; if those cluster, the fix is a new row, not a changed one.
3. **Never apply a blanket multiplier to the total.** Effort doesn't drift
   uniformly, and a single number destroys the information about where the miss
   actually is.

The rubric is shared policy. Changes go through a PR so the team sees the
number move and can argue with the evidence.

If the data doesn't clear the bar, the honest output is: *the logged-time data
is too sparse or too noisy to calibrate against, and here is what would have to
improve* — usually time-logging discipline, which this skill can't fix but
`/log` can help with: it drafts each day's entries from git, so logging stops
depending on memory.

## Reporting

Give the table, the aggregates, the data-quality read, and a recommendation
that is allowed to be "change nothing yet". Never present a ratio as *the*
correction factor without saying how many tickets it rests on and how wide the
spread was.
