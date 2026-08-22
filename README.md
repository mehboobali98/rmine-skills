# rmine-skills

Workflow skills for [Claude Code](https://claude.com/claude-code), built on
[rmine](https://github.com/mehboobali98/rmine) — a Redmine CLI.

`rmine` teaches an assistant how to *drive* Redmine. These skills are the layer
above: multi-step workflows that read a ticket and do something useful with it.

## Skills

| Skill | What it does |
|---|---|
| `/estimate <issue>` | Turns a Redmine ticket into a frontend/backend effort breakdown in hours and points — gated on spec completeness, priced against the actual codebase, then independently reviewed. |
| `/calibrate <paths>` | Compares past estimates against hours actually logged, to find out whether the rubric is systematically optimistic. Reports drift *and* whether the data is good enough to act on. |
| `/spec-interview <issue>` | Audits a spec, routes each gap to whoever can actually close it — code, you, or the requester — and posts the questions that are left back to the ticket, each with the assumption that stands if nobody replies. |

`/estimate` runs three subagents that ship with the plugin, each carrying its own
instructions rather than being briefed by the caller:

| Agent | Role |
|---|---|
| `spec-auditor` | Judges whether the spec can be estimated. Blocks only on gaps that move the hours, and never produces hours itself. |
| `effort-estimator` | Greps the product repo, then prices each line item against the real services and tables it found. |
| `estimate-validator` | Reviews the finished estimate without seeing how it was derived, so it isn't anchored to the estimator's reasoning. |

None of the three can write or edit files.

## Install

```sh
/plugin marketplace add mehboobali98/rmine-skills
/plugin install rmine-skills
```

Prerequisites, all of which `/estimate` checks before it starts:

1. **`rmine` on your `PATH`, with a configured profile.**

   ```sh
   go install github.com/mehboobali98/rmine/cmd/rmine@latest
   rmine config init
   rmine whoami          # should print your Redmine user
   ```

2. **Google Drive connected**, if your specs live in Google Docs — which is the
   most common case. Without it the skill asks you to paste the spec text
   instead of guessing from the ticket subject.

3. **`python3`**, for the `.docx` spec extractor and the `/calibrate` script.
   Stdlib only; nothing to install.

That's the whole setup. There is no calibration file to populate — the rubric
ships with the plugin, so everyone estimates against the same numbers from
their first run.

## Calibration

`/estimate` prices against `skills/estimate/references/rubric.md` — the house
output format, backend and frontend checklists, and a table of hour anchors for
recurring work, derived from real estimates against this team's Rails + React
product.

**The rubric is shared policy, not personal preference.** It ships with the
plugin, so a teammate's estimate and yours are calibrated identically. Changing
an anchor moves everyone's numbers, so changes go through a PR with the
reasoning stated — ideally backed by a `/calibrate` run.

Two things the rubric is deliberately honest about, and which anyone quoting a
number to a customer should know:

- The anchors were derived from **estimates, not outcomes**. They reproduce how
  those estimates were made, systematic error included.
- The AI-assistance compression model is **a judgment about the nature of the
  work, not a measurement**. The direction is sound; the magnitude is unproven.

`/calibrate` is what closes that loop. See below.

`skills/estimate/references/format-examples.md` sits alongside the rubric with
two worked estimates showing the required shape and the level of specificity
expected in a line item. Its numbers are invented on purpose — it teaches
format, never pricing.

## Running it

Run `/estimate <issue>` **from inside the repo the work will land in** — the
estimator greps for the real services and tables a change touches before pricing
anything, which is most of the difference between an estimate and a guess.

Every estimate carries who produced it, when, and a `Confidence` grade with the
reason next to it — graded on how much of the number came from the rubric's
anchor table rather than from judgment, so a point estimate can't be read as
more certain than the spec it came from.

The format is a contract, not a convention: `scripts/check_format.py` checks
arithmetic, the points formula, the required headers and the last-line rule,
and `/estimate` runs it before it reports done. You can run it yourself over
the whole corpus:

```sh
python3 skills/estimate/scripts/check_format.py estimates/
```

Estimates are written to `./estimates/estimate-<id>.md` in that repo. **Commit
them.** That directory is the team's estimate corpus and the only input
`/calibrate` has:

```sh
/calibrate estimates/
```

`/calibrate` matches each estimate to the hours actually logged against its
ticket and reports drift — but it needs 20+ finished tickets before it will
recommend touching an anchor, and it is written to say "the data is too noisy
to act on" rather than hand you a confident multiplier built from four tickets.
An uncommitted estimate on one laptop never counts toward that.

`/estimate` and `/calibrate` write nothing back to Redmine. `/spec-interview`
does — one comment, on a ticket you name, and only after showing you the exact
text and getting a yes. It touches nothing else: no status, no fields, no
assignee.

## License

MIT
