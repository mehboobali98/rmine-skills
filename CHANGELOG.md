# Changelog

Rubric changes move every estimate the team produces, so they are called out
here explicitly. Anchor changes should link the `/calibrate` evidence behind
them.

## 0.4.0

**The house format is a numbered outline, and the tooling now reads one.** This
is a format change, so it moves what every estimate must look like.

### Fixed

- **An estimate written in the real house format was invisible to
  `/calibrate`.** Estimates are written in Google Docs, which numbers every
  outline level and keeps the numbering in the exported text — so the last line
  arrives as `6. Total (16 hrs ~ 4 points)`. `parse_total` matched on `^Total`
  and saw nothing, `parse_estimates` returned an empty list, and the ticket
  simply never entered the corpus. No error, no row, no `no time logged` line:
  the estimate did not exist as far as the analysis was concerned. Both scripts
  now strip an outline marker before matching, and tolerate the `**bold**` the
  header keys carry out of a rich-text doc.
- **`check_format.py` rejected the same estimates**, for the same reason plus
  hard-coded indent widths of 0 and 2 — a Google Docs outline indents by
  whatever Word decided. Nesting is now ranked from the distinct indent widths
  in the file, so a four-level outline and a hand-written two-space indent read
  identically, and `Total` stays level 0 whether or not the outline numbered it.
- **`/calibrate` credited an estimate's hours to a linked ticket instead of the
  one being estimated.** `actuals.py` bound each `Total` to the last
  `/issues/<id>` URL it had seen, wherever it appeared — and `/estimate` tells
  estimators to name the linked tickets they treated as shipped foundations or
  dependencies in `Assumptions:`, where the natural way to write one is a link.
  When that happened the estimated ticket reported `no time logged` and dropped
  out of the corpus, while the linked ticket was scored against an estimate
  never made for it, putting a fabricated ratio straight into the weighted
  aggregate. The `Redmine:` header now claims the `Total` and nothing can take
  it; a bare URL still works for estimates written before that header existed.
- **`check_format.py` printed `ok` for files it had only partly read.** In a
  file holding several estimates it validated the last one and skipped the
  rest, which is the worst possible failure for a checker whose job is stopping
  estimates from silently dropping out of the corpus. It now splits on the
  `Total` line and checks every estimate, reporting problems against the real
  line numbers. Content after the final `Total` is named as trailing content
  rather than reported as a malformed estimate.
- **`estimate-validator`'s checklist started at item 4** and told the agent to
  work through "4-10" while item 11 sat below it — items 1-3 had been replaced
  by `check_format.py` in 0.3.0 without renumbering. Renumbered 1-8, with the
  confidence check inside the range the agent is pointed at.

### Changed

- **A line item without hours is legal, and descriptive.** Real estimates use
  them constantly — `New KPIs handling in:` names what a section covers without
  claiming a slice of it — and the checker used to fail every one as "line item
  carries no hours". Priced siblings still have to sum to the section, so this
  hides nothing.
- **`rubric.md` documents the outline** as the output format, states that
  nesting rather than marker style is what carries meaning, and says plainly
  that flattening an estimate destroys it. Marker style and bold header keys
  are both optional; depth is not.
- **`format-examples.md` is rewritten as two numbered outlines**, and no longer
  contradicts the rubric it illustrates. Unpriced descriptive line items are a
  fourth reading added to what the entries teach. The first entry totals 8.5
  hrs, so Testing now collapses into `Demo + PR Reviews + Testing` as
  `rubric.md` requires under ~10 hrs; the second grew the ability line item it
  was missing from the backend checklist, which puts it over that threshold and
  brings Testing to 14% of dev hours rather than 20%. A note says why the two
  entries differ, since the file is the canonical shape reference and was
  teaching the exception as the norm.
- **`effort-estimator`** is told to emit the outline and when to use an unpriced
  line item.

## 0.3.1

### Fixed

- **`/calibrate` under-counted logged time on every ticket with more than 25
  time entries.** `actuals.py` called `rmine time list` without `--all`, and
  that command returns 25 entries by default — so a ticket with 30 hours across
  30 entries reported 25. The ratio then read low and the row was flagged
  `suspect under-logging`, manufacturing the exact artifact this skill tells
  you is the biggest source of false optimism in the analysis. The bias was not
  even: tickets with the most entries are the largest ones, which dominate the
  weighted ratio. Any calibration run before this fix understated actual hours,
  so re-run it before trusting an earlier result.
- **`test_actuals.py`** now covers the script, including a regression guard on
  `--all`, the non-work split, logger counting, and every `Total` line shape.

## 0.3.0

### Added

- **`scripts/check_format.py`** — a deterministic checker for the house format:
  section and total arithmetic, `points = round(hours / 4)` half-up, 0.25
  granularity, the required header lines, `Assumptions:` above `Breakdown:`,
  `Total` as the literal last line, `N/A` rather than an omitted layer, and a
  `Discussions` buffer whose gaps are actually named. `/estimate` runs it before
  reporting done, and `estimate-validator` runs it first so it can spend its
  attention on the judgment checks instead of re-deriving arithmetic.
  `test_check_format.py` covers it, 15 cases.
- **Provenance and confidence on every estimate.** New required header lines:
  `Estimated by`, `Date` (ISO), and `Confidence: High|Medium|Low` with the
  reason next to it. Confidence is graded on how much of the estimate came from
  the anchor table rather than on how the estimator feels, so a point number
  can't be read as more certain than the spec behind it. `Estimated by` and
  `Date` also give `/calibrate` per-person drift and make a stale estimate
  visible.

### Changed

- **`spec-auditor` now attaches a recommended answer to every `WORTH ASKING`
  question** (`Q:` / `A:` pairs), and `/estimate` puts it first in
  AskUserQuestion as `(Recommended)`. A bare question asks the reader to do the
  thinking; a question with a recommendation asks them to correct it, which is
  cheaper to answer and likelier to get a reply. Unanswered questions now carry
  their recommendation into `Assumptions:` instead of vanishing. Borrowed from
  the `grilling` skill in mattpocock/skills.
- An `INCOMPLETE` verdict now points at fixing the spec — a grilling or
  spec-interview skill — rather than just stopping. Overriding it drops
  `Confidence` to `Low`.

## 0.2.0

Prepared the plugin for team-wide use. **The estimate pipeline no longer reads a
private samples file.**

### Changed

- **Calibration now comes from `skills/estimate/references/rubric.md` alone.**
  Previously the anchor table was a fallback and a gitignored
  `samples.local.md` was the primary signal — which meant it was absent on
  every fresh install, and each person's calibration drifted independently.
  The rubric ships with the plugin, so everyone estimates against the same
  numbers from their first run. The anchors were derived from those samples, so
  their influence is preserved; it is now shared, reviewable and versioned.
- `samples.example.md` → `format-examples.md`, reframed as a format and
  specificity reference. Its numbers are invented and the estimator is told not
  to anchor to them.
- The AI-assistance section of the rubric is now an explicit switch the caller
  sets, defaulting to on. Which way it ran must appear in `Assumptions:`.
- Estimates are written to `./estimates/estimate-<id>.md` in the product repo
  and are meant to be committed. That directory is the team's estimate corpus
  and the only input `/calibrate` has.
- `/calibrate`'s recommendation list dropped "annotate the samples" — the
  mechanism it relied on is gone — and now leads with adjusting individual
  anchor rows via PR, with the evidence named.

### Added

- A preflight step in `/estimate`: `rmine whoami` covers a missing binary, an
  unconfigured profile and bad credentials in one call, and the skill points at
  the fix instead of failing halfway through the run.
- A scope header on the rubric naming the codebase it was calibrated against,
  and an ownership note stating that changes go through a PR.
- README prerequisites now list Google Drive and `python3` alongside `rmine`.

### Fixed

- `estimate-validator` was told to check pricing "against the closest
  comparable past estimate", but is deliberately given only the spec and the
  estimate — it never had the samples. It now checks against the rubric's
  anchor table and flags line items that borrow a row that doesn't fit.

## 0.1.0

Initial release: `/estimate` and `/calibrate`, with the `spec-auditor`,
`effort-estimator` and `estimate-validator` agents.
