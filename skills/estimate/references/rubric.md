# Estimation rubric

The house format and the team's calibration. This file is the single source of
truth for both — the estimator prices against the anchor table below, and
`format-examples.md` shows the shape the output must take.

**Scope: the Rails + React product this team works on.** The anchors were
derived from a body of real estimates against that codebase. They are not
industry averages and they do not transfer to a different repo — see
`## Known bias` at the bottom before trusting a number produced elsewhere.

**Owner:** this rubric is shared policy, not personal preference. Changing an
anchor changes everyone's numbers, so changes go through a PR with the
reasoning stated, ideally backed by a `/calibrate` run. See `## Known bias`
for the bar a calibration result has to clear.

## Output format

The breakdown is a **numbered outline** — one level per degree of nesting,
the way it comes out of a Google Doc:

```
**Task**: <task name>
**Redmine**: <issue URL>
**Estimated by**: <name>
**Date**: <YYYY-MM-DD>
**Confidence**: <High|Medium|Low> — <the one thing driving it>
**Mode**: <agent-driven|hand-written>
**Range**: <low>–<high> hrs                    ← required in agent-driven mode
**Assumptions**:
    <what the number depends on — linked tickets treated as shipped,
     non-blocking gaps priced into Discussions, lines priced above their
     agent-driven row and why, the lines that set the top of the range,
     least-confident areas>
**Breakdown**:
    1. Backend (X hrs)
        a. <line item> (N hr)
            i. <sub-detail, no hours of its own>
        b. <line item, unpriced — describes what the section covers>
    2. Frontend (Y hrs)
        a. <line item> (N hr)
    3. Testing (T hrs)
    4. Demo + PR Reviews (D hrs)
    5. Discussions + Additional cases: B hours     ← only when the spec is fuzzy
        a. <the gap these hours buy>
    6. Total (Z hrs ~ P points)
```

Rules that hold on every estimate:

- **`Total (Z hrs ~ P points)` is the literal last line**, outline number and
  all. Downstream tooling parses it. Don't reword it, don't add a summary after
  it.
- **Nesting is what carries meaning**, not the marker style. `1. / a. / i. / 1.`
  is what a Google Doc produces and what the corpus mostly holds, but a plain
  two-space indent with no markers reads identically to the tooling. Bold on the
  header keys is likewise optional. What matters is that each level sits deeper
  than the one above it — flatten an estimate and its structure is gone.
- **A line item without hours is descriptive**, naming what the section covers
  rather than claiming a slice of it. Its priced siblings still have to add up
  to the section, so nothing hides behind one.
- **`points = round(hours / 4)`**, standard rounding. 26.5→7, 10.5→3, 6.75→2,
  65→16, 29.5→7. Below ~4 hrs the points figure is often dropped entirely.
- **Granularity is 0.25 hr.** In practice the values used are 0.25, 0.5, 1, 2,
  4, 6, 8. A line item priced at 3.5 is a line item that wants splitting.
- **Section hours must equal the sum of their line items**, and the total must
  equal the sum of the sections. This is checked.
- **A layer that isn't touched gets `N/A`, not omission.** `Frontend (N/A)`
  says "considered, nothing needed"; a missing heading says "forgot".
- Sub-details sit under a priced line item without prices of their own — they
  justify the number, they don't subdivide it. Nest them as deep as the work
  needs; the checker only cares that they are deeper than the item they explain.
- **`Mode:` is `agent-driven` or `hand-written`** — see `## Work mode`. An
  agent-driven estimate also carries `Range: <low>–<high> hrs`, and the Total
  sits inside it.
- **The header lines are all required.** `check_format.py` enforces every rule
  in this section, so an estimate that drifts fails loudly instead of silently
  dropping out of the calibration corpus.

## Confidence

A total is a point number, and a point number reads as more certain than the
spec it came from. The `Confidence:` line is what stops that, and it is graded
on **how much of the estimate came from the anchor table** rather than on how
the estimator feels:

- **High** — nearly every line item priced from a matching anchor row, against
  an existing in-repo pattern the estimator read.
- **Medium** — a few line items had no close anchor row, or a pattern the work
  depends on couldn't be confirmed in the codebase.
- **Low** — a `Discussions` line was needed, or several line items are
  judgment rather than calibration. A Low estimate is a range presented as a
  number; say so when handing it to anyone.

Always name the one thing driving the grade. `Confidence: Medium` alone tells
a reader nothing they can act on; `Confidence: Medium — no anchor row covers
the third-party sync, priced from the 4+ single-value anchor` tells them
exactly which line to push back on.

Who and when are there for the same reason plus one more: `/calibrate` can
read per-person drift off `Estimated by`, and `Date` is what makes a stale
estimate visible when the ticket has moved on since.

## The non-development lines

- **Testing** — its own line, roughly 10–15% of dev hours in either mode. Under
  ~10 hrs total, it collapses into `Demo + PR Reviews + Testing (N hr)`. In
  agent-driven mode the agent writes the specs; the hours are deciding what to
  verify and reading what it wrote.
- **Demo + PR Reviews**
  - *Hand-written:* 2 hrs is the default and covers most tasks. 0.5 for
    something trivial, 4 when the task is 50+ hrs.
  - *Agent-driven:* this is where most of the developer's time now goes, so it
    is priced from what the spec touches rather than as a flat figure. About
    1–2 hrs for each screen or user flow someone has to click through (browser
    checks, UI feedback rounds), 0.5 for each backend area whose diff needs a
    careful read (permissions, data changes), and 0.5–1 for the demo. Write
    them as line items under the section. Provisional: on the ticket behind
    [issue #8](https://github.com/mehboobali98/rmine-skills/issues/8), review,
    demo and discussions took 8 of 25 hrs, the only part of the estimate that
    ran over.
- **Discussions + Additional cases** — 2–4 hrs, and only when the spec left
  real questions open. This is where acknowledged uncertainty gets priced
  instead of being smuggled into padded line items. If the auditor flagged
  non-blocking gaps, they belong here with the gaps named.

  **Name the gaps, or drop the line.** The common failure is buying the same
  risk twice: an ambiguity that was already answered in the ticket comments, or
  a late addition that already has its own priced line item, doesn't get to be
  bought again here. If you can't name what the hours are for, they aren't
  uncertainty — they're padding.

## Backend checklist

Walk it in order; most backend work is some subset, and a missing step is the
single most common way an estimate comes in low.

1. Schema change / migration — name the tables and columns
2. Model: associations, validations, scopes
3. Controller, routes, ability (permissions)
4. Presenter and serializer
5. List view preference (which columns the listing exposes)
6. Filters — say whether an existing pattern covers it
7. Rake task to backfill or seed **existing** tenants
8. Side menu / settings exposure
9. Search integration when the resource must be findable

Steps 7 and 9 are the ones most often forgotten. Anything landing in a
multi-tenant table needs a story for the tenants that already exist.

## Frontend checklist

1. Redux slice / state shape
2. Action creator and action mapper
3. API method
4. Parser and model
5. Container and screen
6. Modal UI, confirmation dialogs
7. Mass actions
8. Settings toggle exposure

## Calibration anchors

Typical hours for recurring work. This table is the calibration — price
against it directly, and say so in the line item when a piece of work has no
close match here.

Price from the column for the estimate's `Mode:` — see `## Work mode`. The
**Agent-driven** column is the developer's time when an agent writes the code.
**Basis** says what each agent-driven figure rests on: *measured* rows come from
a postmortem, *held* rows stayed inside their hand-written range on one, and
*judgment* rows haven't been measured yet. The whole column is provisional
until postmortems confirm it; see `## Known bias`.

| Work | Hand-written | Agent-driven | Basis |
|---|---|---|---|
| New column + migration | 0.25–0.5 | 0.25–0.5 | held (#8) |
| Model only (associations, validations) | 0.25–1 | 0.25–1 | held (#8) |
| Controller + routes + ability + CRUD actions | 2–4 | 0.5–1 | measured once (#8) |
| Presenter or serializer changes | 0.25–1 | 0.25–1 | held (#8) |
| List view preference | 0.5–2 | 0.25–0.5 | measured once (#8) |
| Filters on an existing pattern | 1–2 | 0.25–0.5 | judgment |
| Rake task to backfill existing tenants | 1–4 | 0.5–2 | judgment |
| Global / elastic search integration | ~4 | 1–2 | judgment |
| Permission handling across a module | 5–8 | 2–4 | judgment |
| Sync / integration logic against a third-party API | 4+ | 2+ | judgment |
| New full listing screen (FE) | 4–6 | 1–2 | judgment |
| Modal + redux + action mapper (FE) | ~2 | 0.75–1 | measured once (#8) |
| Adding a column to an existing listing (FE) | 0.5–1 | 0.5–1 | held (#8) |
| Settings toggle exposure (FE) | 0.25–0.5 | 0.25 | judgment |
| Canvas / visualization work reusing existing code | ~4 | 0.5–1 | measured once (#8) |
| Canvas / visualization element with no in-repo pattern | ~2 | 0.5–1 | measured once (#8) |

## Work mode

**Every estimate is priced in one of two modes, and the `Mode:` header says
which.** The same ticket can price more than twice apart between them, and a
reader who can't tell which they're holding will misread the number.

- **`agent-driven` — the default.** An agent writes the code. The developer
  plans the work, describes it to the agent, steers and reviews the diff, checks
  that it works, and demos it. A line's hours are that developer time, not the
  time it would take to type the code. Price from the **Agent-driven** column.
- **`hand-written`.** A person writes the code. Price from the **Hand-written**
  column, as written. Use it only when the caller says the work will be typed by
  hand.

There is still no multiplier to apply to a total. Each row carries its own
agent-driven figure, because an agent doesn't shorten every kind of work by the
same amount.

### Pricing agent-driven work

For each line the question is not *how long does this take to build*. It is how
long the developer will spend on three things:

1. **Describing it to the agent** — reading the code it touches, deciding the
   approach, writing the task.
2. **Steering and reviewing the diff** until it is right.
3. **Checking that it works** — running it, clicking through it, trying the
   edge cases.

That holds for new work as much as for routine work. An agent writes code with
no in-repo pattern about as fast as code with twenty examples to copy, so
novelty doesn't keep a line at hand-written size. On the ticket behind
[issue #8](https://github.com/mehboobali98/rmine-skills/issues/8), ten canvas
lines with mostly no pattern to follow took 7 hrs against 21.25 estimated,
about a third; the routine rows came in at an eighth to a half of theirs.

**A line priced above its agent-driven row needs a named reason in its
sub-detail.** An agent speeds up least the work whose time goes into waiting,
deciding or checking real data rather than writing:

- debugging against a live third-party API;
- UX back-and-forth with stakeholders;
- migrations and backfills run against customer data;
- performance work that has to be measured against production-sized data.

A line with no close anchor row is priced the same way, by the three questions,
and listed in `Assumptions:` as judgment.

**Distrust your own sense of effort.** Whoever prices or reviews an estimate,
person or model, learned how long code takes from code typed by hand. On
agent-driven work that sense runs high, by as much as two and a half times.
When a line feels too cheap, check it against the Agent-driven column, not
against instinct.

### The range

An agent-driven `Total` is the likely case, not a promise. When the agent gets a
line right first time it is quick; when it takes a wrong turn, the cost is extra
review rounds. So every agent-driven estimate carries a `Range:` line:

- **low end** — every line goes as described;
- **high end** — the lines most likely to go wrong take extra review rounds.
  Name them in `Assumptions:`.

The Total sits inside the range. The range stays until postmortems have measured
the Agent-driven column — see `## Known bias`.

## Line items name real things

The difference between a useful estimate and a guess is specificity. Write
`Update TriggerCustomActionService to handle multiple resources (2 hr)`, not
`Update the service (2 hr)`. Grep the codebase for the actual class, table and
file names before pricing anything — if a line item can't name what it touches,
that's a sign the spec is vague there, and it belongs in the Discussions line.

## Known bias

These anchors encode one estimator's calibration on one codebase over a few
months. They are not industry averages and won't transfer to another repo.

They were derived from **estimates, not outcomes** — which means they reproduce
how that estimator estimated, including any systematic error. Shared across a
team, that error is now shared too: everyone is wrong in the same direction,
which is easier to detect and correct than everyone being wrong differently,
but it is still wrong until measured.

Run `/calibrate` to measure it against hours actually logged. Expect the first
run to be inconclusive rather than corrective: logged time is what people
remembered to type in, and a corpus where few tickets land near their estimate
is measuring logging habits, not estimation error. `/calibrate` documents the
bar a result has to clear before any anchor here should move.

Until it clears that bar, **no correction is applied to the hand-written
column, deliberately** — a confident multiplier derived from noisy data is
worse than an acknowledged unknown. Treat the anchors as an unvalidated starting
point, and say plainly that the calibration is unproven when an estimate is
going somewhere it matters.

The **Agent-driven** column is younger and thinner still. Its *measured* rows
rest on one postmortem, and its *judgment* rows on nothing but the measured
ones. It went in before `/calibrate`'s bar could be met, also deliberately: it
replaced a rule that could only move a line within its hand-written range,
which on the ticket behind issue #8 could discount 8.5 of an estimate's 60.25
hrs when the work took 25. A provisional figure is better than one known to
run as much as two and a half times high. Grow it the way the hand-written
column should have been grown: a `/postmortem` for each finished agent-driven
ticket, and a PR naming them whenever a row moves.
