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

Requires `rmine` on your `PATH` with a configured profile:

```sh
go install github.com/mehboobali98/rmine/cmd/rmine@latest
rmine config init
```

## Calibrating `/estimate`

Out of the box the skill estimates from `skills/estimate/references/rubric.md`
— a generic Rails/React rubric with hour anchors for recurring work.

It gets substantially better when it can read your own past estimates. Put them
in `skills/estimate/references/samples.local.md`; the closest comparable sample
beats any lookup table. That path is gitignored, because real estimates name
internal services, tickets and customers and this repo is public.

If your estimates live in a Word document:

```sh
python3 skills/estimate/scripts/docx2txt.py estimates.docx \
  > skills/estimate/references/samples.local.md
```

The skill runs without it, and says so in its output when it's missing.

## Running it

Run `/estimate` **from inside the repo the work will land in** — the estimator
greps for the real services and tables a change touches before pricing
anything, which is most of the difference between an estimate and a guess.

Specs held in Google Docs need Google Drive access connected; otherwise the
skill asks you to paste the text.

Estimates are written to `./estimate-<id>.md`. Nothing is written back to
Redmine.

## License

MIT
