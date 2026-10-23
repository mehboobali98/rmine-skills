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

### `/demo`, next steps

`/demo` records plain footage of a local app. Three things it leaves out on
purpose, each worth its own step:

1. **A voice-over cut.** A separate skill that takes `demo.mp4` and
   `demo-chapters.json` and adds narration. Plain footage is enough for PM and
   QA; a narrated cut is for people who weren't in the conversation.
2. **Recording against staging.** Local only for now, because every developer
   signs in with their own local account. Staging needs a shared way to sign
   in that keeps passwords out of the skill.
3. **Videos on Google Drive.** Redmine's attachment limit caps how long a demo
   can be. When Google Drive for desktop is set up, copy `demo.mp4` into its
   synced folder, share it with a group the user names, and post the link
   instead of the file. The Drive connector can't carry the upload itself: it
   takes the file as base64 text inside one message, which is too big even for a
   short video. Fall back to the attachment when Drive isn't set up.

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

3. **Anchor-row attribution inside `/calibrate`.** `/calibrate` says to prefer
   fixing the specific anchor row over a blanket multiplier, but it can only
   report whole-ticket ratios. `/postmortem`'s `rollup.py` now gives the
   row-level view from postmortems, which covers only the tickets someone
   postmortemed; reading rows straight from every estimate in the corpus still
   needs line items to name their anchor row parseably.

4. **`/calibrate --audit`.** How many corpus files fail `check_format.py`, how
   many tickets have no logged time. Corpus health before corpus analysis.

5. **`check_format.py --strict`** for the soft rubric rules a script *can*
   compute: Testing at 10–15% of dev hours, the ~10 hr collapse threshold, the
   hand-written Demo defaults by task size.

## Releasing

Use `claude plugin tag` rather than `git tag` — it creates the same
`{name}--v{version}` tag and validates that `plugin.json` agrees with the
marketplace entry first.
