# Changelog

Rubric changes move every estimate the team produces, so they are called out
here explicitly. Anchor changes should link the `/calibrate` evidence behind
them.

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
