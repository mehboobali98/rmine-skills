# Roadmap

What's next, and why each item earns its place. Written down because the
reasoning is the part that gets lost — an idea without the argument behind it
looks arbitrary six weeks later, and gets dropped or half-built.

Ordered by how much each closes a gap the plugin *already has*, not by how
interesting it is to build.

## Skills

### `/scope-drift <issue>` — read the `Date:` header something finally

`Date:` exists so a stale estimate is visible. Nothing reads it.

Compares the ticket now against what was estimated then, and flags scope added
since. Also protects the corpus: a ratio computed for a ticket whose scope
doubled is noise being counted as signal.

### Deliberately not building

`/standup` and `/triage`. Useful, but they are `rmine` conveniences rather than
estimation workflow, and the `rmine` skill already teaches an assistant to run
those queries directly. This plugin's strength is doing one thing with unusual
rigor; a grab-bag dilutes that.

## Tooling

1. **A fixture built from a real committed estimate.** This is the gap that let
   the 0.4.0 outline bug survive three releases: every test sample was written in
   a format nobody actually uses, so the suites agreed with each other and none
   of them agreed with reality. Highest-leverage item in this section.

2. **Per-person drift.** `Estimated by` is captured on every estimate and
   `rubric.md` promises `/calibrate` reads it. `actuals.py` never parses it.

3. **Anchor-row attribution.** `/calibrate` says to prefer fixing the specific
   anchor row over a blanket multiplier, but it can only report whole-ticket
   ratios — it structurally cannot produce the recommendation it tells you to
   prefer. Needs line items to name their anchor row parseably.

4. **`/calibrate --audit`.** How many corpus files fail `check_format.py`, how
   many tickets have no logged time. Corpus health before corpus analysis.

5. **`check_format.py --strict`** for the soft rubric rules a script *can*
   compute: Testing at 10–15% of dev hours, the ~10 hr collapse threshold, the
   Demo defaults by task size.

## Releasing

Use `claude plugin tag` rather than `git tag` — it creates the same
`{name}--v{version}` tag and validates that `plugin.json` agrees with the
marketplace entry first.
