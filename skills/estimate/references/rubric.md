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

```
Task: <task name>
Redmine: <issue URL>
Assumptions:
  <what the number depends on — whether AI assistance was applied, linked
   tickets treated as shipped, non-blocking gaps priced into Discussions,
   least-confident areas>
Breakdown:
Backend (X hrs)
  <line item> (N hr)
    <sub-detail, no hours of its own>
Frontend (Y hrs)
  <line item> (N hr)
Testing (T hrs)
Demo + PR Reviews (D hrs)
Discussions + Additional cases: B hours        ← only when the spec is fuzzy
Total (Z hrs ~ P points)
```

Rules that hold on every estimate:

- **`Total (Z hrs ~ P points)` is the literal last line.** Downstream tooling
  parses it. Don't reword it, don't add a summary after it.
- **`points = round(hours / 4)`**, standard rounding. 26.5→7, 10.5→3, 6.75→2,
  65→16, 29.5→7. Below ~4 hrs the points figure is often dropped entirely.
- **Granularity is 0.25 hr.** In practice the values used are 0.25, 0.5, 1, 2,
  4, 6, 8. A line item priced at 3.5 is a line item that wants splitting.
- **Section hours must equal the sum of their line items**, and the total must
  equal the sum of the sections. This is checked.
- **A layer that isn't touched gets `N/A`, not omission.** `Frontend (N/A)`
  says "considered, nothing needed"; a missing heading says "forgot".
- Sub-details sit under a priced line item without prices of their own — they
  justify the number, they don't subdivide it.

## The non-development lines

- **Testing** — its own line, roughly 10–15% of dev hours. Under ~10 hrs total,
  it collapses into `Demo + PR Reviews + Testing (N hr)`.
- **Demo + PR Reviews** — 2 hrs is the default and covers most tasks. 0.5 for
  something trivial, 4 when the task is 50+ hrs.
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

The **Compresses** column is how much AI-assisted coding is expected to reduce
the work — see the section below for how to apply it.

| Work | Hours | Compresses |
|---|---|---|
| New column + migration | 0.25–0.5 | High |
| Model only (associations, validations) | 0.25–1 | High |
| Controller + routes + ability + CRUD actions | 2–4 | Medium |
| Presenter or serializer changes | 0.25–1 | High |
| List view preference | 0.5–2 | High |
| Filters on an existing pattern | 1–2 | High |
| Rake task to backfill existing tenants | 1–4 | Medium |
| Global / elastic search integration | ~4 | Low |
| Permission handling across a module | 5–8 | Low |
| Sync / integration logic against a third-party API | 4+ | Low |
| New full listing screen (FE) | 4–6 | High |
| Modal + redux + action mapper (FE) | ~2 | High |
| Adding a column to an existing listing (FE) | 0.5–1 | High |
| Settings toggle exposure (FE) | 0.25–0.5 | High |
| Canvas / visualization work reusing existing code | ~4 | Low |

## AI-assisted development

**This section is a switch, and the caller decides which way it is set.** The
default is on: the team codes with an AI assistant day to day. When it is off,
ignore this section entirely and use the anchor ranges as written — unmodified
is what they were derived from.

Either way, the `Assumptions:` block must say which way it ran. Two estimates
for the same ticket differ materially depending on this, and a reader who
can't tell which they're holding will misread the number.

Assistance does not scale work down uniformly, so there is no single multiplier
to apply to a total. It compresses **pattern-following work** — code where the
codebase already contains twenty examples of the same shape, and the job is
producing the twenty-first correctly. It barely touches **judgment,
integration, and coordination work** — deciding who may see what, debugging
against a live third-party API, iterating on UX, agreeing scope in a demo.

How to apply it:

- **High** — price at the **bottom** of the anchor range.
- **Medium** — price at the **middle**.
- **Low** — the range stands, unchanged.
- Single-value anchors (`~4`, `4+`) have no range to move within. Leave them
  and say so in the line item rather than inventing a discount.

Two consequences worth stating explicitly, because a flat multiplier gets both
wrong:

1. **The non-development lines do not compress at all.** Demo, PR reviews, and
   the Discussions buffer are human coordination. Testing compresses somewhat
   for writing specs, not for deciding what to verify. As dev hours come down
   these become a *larger* share of the total, not a proportional one.
2. **Unfamiliar work compresses least.** Assistance is most effective where
   there is an established in-repo pattern to follow, which is exactly the work
   that was cheap to begin with. A genuinely novel service gains the least.

**This split is a judgment about the nature of the work, not a measurement.**
Nothing here has been validated against hours actually logged. Treat the
direction as sound and the magnitude as unproven.

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

Until it clears that bar, **no correction is applied to these anchors,
deliberately** — a confident multiplier derived from noisy data is worse than
an acknowledged unknown. Treat the anchors as an unvalidated starting point,
and say plainly that the calibration is unproven when an estimate is going
somewhere it matters.
