---
name: calibrate
description: Compare past effort estimates against hours actually logged in Redmine, to find out whether the estimation rubric is systematically optimistic or pessimistic. Use when the user asks how accurate their estimates are, wants to calibrate or tune the estimate rubric, asks about estimate vs actual, estimation drift, or whether a team consistently over- or under-estimates.
---

# Calibrate

`/estimate` learns from past **estimates**, so it reproduces how someone
estimates — including any systematic error. This skill is the only thing that
can tell you whether those estimates were any good.

```sh
python3 <skill-dir>/scripts/actuals.py <path>...
```

Accepts a samples file holding many estimates, individual `estimate-<id>.md`
files, or a directory of them. It parses each estimate's issue reference and
`Total` line, pulls matching time entries via `rmine time list`, and reports a
ratio per ticket plus aggregates.

The script does the arithmetic. **Interpreting it is the hard part, and doing it
wrong is worse than not running it** — a confidently wrong multiplier applied
across a team's estimates is a lot of damage from one bad inference.

## Read the data quality before reading the numbers

Logged time is not ground truth. It is what people remembered to type in. Check
all of these before drawing any conclusion:

- **`within +/-25%` count.** This is the headline. If most tickets don't land
  near their estimate, there is no systematic drift to correct — there is noise.
  A median of 0.8 built from ratios of 0.05 and 2.96 is not "20% optimistic",
  it's an average of unrelated numbers.
- **`suspect under-logging` flags** (ratio < 0.5). A shipped ticket with a
  fraction of its estimate logged did not take a fraction of the time. Someone
  logged elsewhere, or not at all. These drag the aggregate down and are the
  single biggest source of false optimism in this analysis.
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
  planning cares about, and is dominated by the largest tickets.
- **Median** is the typical ticket, and ignores size.

When they diverge, drift is not uniform — most likely small tickets and large
tickets behave differently. Say that, rather than picking whichever number
supports the change you were going to make.

## What to actually change

**Default to changing nothing.** The bar for touching
`skills/estimate/references/rubric.md` is high:

- more than half the tickets within ±25%, **and**
- few under-logging flags, **and**
- weighted and median pointing the same direction, **and**
- enough tickets that a couple of outliers can't set the result — 20+.

Only then is there a signal. Even then, prefer the specific fix to the global
one, in this order:

1. **Annotate the samples.** Add the actual to each entry in
   `samples.local.md`: `Total (12 hrs ~ 3 points) — actual: 25 hrs`. The
   estimator anchors on the closest comparable sample, so this corrects
   calibration where it's wrong without touching a single anchor. Cheapest and
   most precise change available.
2. **Adjust individual anchors** whose work type shows consistent drift across
   several tickets.
3. **Never apply a blanket multiplier to the total.** Effort doesn't drift
   uniformly, and a single number destroys the information about where the miss
   actually is.

If the data doesn't clear the bar, the honest output is: *the logged-time data
is too sparse or too noisy to calibrate against, and here is what would have to
improve* — usually time-logging discipline, which is a team habit and not
something this skill can fix.

## Reporting

Give the table, the aggregates, the data-quality read, and a recommendation
that is allowed to be "change nothing yet". Never present a ratio as *the*
correction factor without saying how many tickets it rests on and how wide the
spread was.
