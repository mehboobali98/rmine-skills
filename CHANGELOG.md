# Changelog

Rubric changes move every estimate the team produces, so they are called out
here explicitly. Anchor changes should link the `/calibrate` evidence behind
them.

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
