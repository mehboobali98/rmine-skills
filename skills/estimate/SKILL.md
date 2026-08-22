---
name: estimate
description: Turn a Redmine ticket into a frontend/backend effort estimate in hours and points, via a spec-completeness gate, a codebase-aware estimator, and an independent validator. Use when the user asks to estimate a ticket, scope a spec, break down effort, produce an ETA, or asks "how long will <issue> take". Run from inside the product repo being estimated.
---

# Estimate

Given a Redmine issue, produce the house-format effort breakdown. Three agents,
each shipped with this plugin and carrying its own instructions:

| Agent | Role |
|---|---|
| `spec-auditor` | Refuses to estimate an unusable spec. Never produces hours. |
| `effort-estimator` | Prices the work against the actual codebase. |
| `estimate-validator` | Reviews the result without seeing how it was derived. |

You orchestrate: gather the spec, run them in order, gate on the auditor,
reconcile the validator's findings. **Their prompts live in their own
definitions — don't paraphrase them here**, or the constraints degrade with
every relay.

Run this from inside the repo the work will land in. Without the codebase the
estimate degrades to generic guesswork — say so plainly rather than pretending
otherwise.

## 0. Preflight

Check these before touching the ticket. Each one fails silently or confusingly
halfway through otherwise, which is a bad first run for someone new to the
plugin.

```sh
rmine whoami
```

One call covers all three failure modes: `rmine` missing from `PATH`, no
profile configured, or credentials that don't authenticate. If it fails, stop
and point at the fix — `go install github.com/mehboobali98/rmine/cmd/rmine@latest`
then `rmine config init` — rather than continuing into an error.

Then confirm two things about where you are:

- **You are inside the product repo**, not this plugin's repo and not a home
  directory. The estimator greps for real services and tables; run anywhere
  else and it prices from imagination.
- **AI-assistance is on or off.** The rubric defaults to on. If the user hasn't
  said, assume on and record it in `Assumptions:` — don't ask, but never leave
  it unstated, because the same ticket prices differently either way.

Google Docs specs additionally need Google Drive connected. You'll find out in
step 1; don't pre-check it.

## 1. Get the spec

Accept a Redmine URL or a bare issue ID.

```sh
rmine issue view <id> --comments -o json
```

Comments matter: scope changes and clarifications routinely live there rather
than in the description. Skip journal entries with empty `notes` — those are
bare field changes.

The spec itself lives in one of four places. Check in this order:

1. **A Google Docs link in the description.** The most common case. Read it
   with the Google Drive tools. If Drive isn't authenticated, say so and ask the
   user to paste the spec text — do not guess from the ticket subject.
2. **An attached document.**
   ```sh
   rmine issue attachments <id> --download <scratch-dir>
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/estimate/scripts/docx2txt.py" <scratch-dir>/<file>.docx
   ```
   The script handles `.docx` only and exits non-zero on anything else; when it
   does, ask for the text rather than continuing with nothing.
3. **The description itself**, when it's substantial prose rather than a link.
4. **Nothing.** An empty description with no attachment and no link is not a
   spec. Stop and say so.

### Linked issues

Specs reference sibling tickets constantly — *"as defined in the json schema
(issues/NNNNN)"* is a hard dependency on another ticket's scope, and estimating
without reading it is estimating half-blind.

Pull every `issues/<id>` reference out of the description **and** the comments,
then `rmine issue view <id>` each one. For each, establish:

- is it **shipped**? Then its behaviour is a fixed foundation to build on.
- is it **unshipped**? Then it's a dependency, and that's a blocking gap.
- does it **overlap** in scope? Then say which side owns which work, or the
  same hours get estimated twice across two tickets.

Two levels deep is plenty; don't crawl the whole graph.

Combine the spec, the comments, and what the linked issues establish into one
spec text. Everything downstream works from that.

## 2. Auditor — the gate

Launch the **`spec-auditor`** agent with the spec text **and nothing else**: no
rubric, no codebase paths, no mention of estimating. Its own definition carries
the checklist and the blocking bar — don't restate them, and don't add anything
that primes it to produce hours.

It returns `READY` or `INCOMPLETE`, plus blocking gaps, non-blocking gaps, and
anything `WORTH ASKING`.

**If `INCOMPLETE`:** print the blocking gaps, stop, don't estimate. The right
next move is fixing the spec rather than estimating it anyway — point at
`/spec-interview <id>`, which ships with this plugin, runs the same auditor, and
writes the answers back to the ticket. The user can also override by saying so,
in which case each gap becomes a stated assumption, the `Discussions` line
widens, and `Confidence` drops to `Low`.

**If it returned `WORTH ASKING` items:** ask them with AskUserQuestion *before*
estimating, batched, at most three. A gap a tech lead closes in one sentence is
worth 30 seconds of their attention and can move a line item 3x. Anything the
codebase can answer, let the estimator answer by reading code — don't spend the
user's attention on it.

Each item arrives as a `Q:`/`A:` pair. **Put the auditor's recommended answer
first, labelled `(Recommended)`.** That turns "do my thinking for me" into
"correct me if I'm wrong" — much cheaper to answer, and it means a user who
skips the question still gets a stated assumption rather than a silent one.
Whatever they don't answer, carry the recommendation into `Assumptions:`.

## 3. Estimator

Launch the **`effort-estimator`** agent from the repo the work lands in. Pass it:

- the spec text
- `${CLAUDE_PLUGIN_ROOT}/skills/estimate/references/rubric.md` — the format and
  the calibration anchors
- `${CLAUDE_PLUGIN_ROOT}/skills/estimate/references/format-examples.md` — two
  worked estimates showing the shape and the level of specificity. **Their
  numbers are invented**; say so when you pass the path, so nothing anchors to
  them
- whether AI-assistance is on or off
- any answers you got from the `WORTH ASKING` questions

Its definition already covers grepping before pricing, pricing against the
anchor table, and the output format. Don't re-explain them.

## 4. Validator

Write the spec and the finished estimate to two files **in a scratch
directory, not the product repo** — they are pipeline intermediates and
committing them would pollute the estimate corpus. Then launch the
**`estimate-validator`** agent with **nothing in its prompt but those two
paths**.

Passing paths rather than inline content is the whole discipline here. Inline
content invites summarising, and summarising is how the estimator's reasoning
leaks in — at which point this stops being an independent check and becomes an
expensive agreement. Two paths and a sentence naming which is which.

**Never pass the estimator's reasoning, greps, or intermediate notes**, in any
form. Its definition tells it to report the leak if you do; treat that as a real
failure, not a formality.

## 5. Reconcile and write

Apply the validator's findings. Where you disagree with it, say why in one
line rather than silently dropping it.

Print the breakdown, then write it to `./estimates/estimate-<id>.md` in the
product repo, creating the directory if it doesn't exist. Keep the format in
`rubric.md` exactly — `Total (Z hrs ~ P points)` is the literal last line so a
later estimate-vs-actual pass can parse a directory of these without guessing.

Fill the header from what you already have: `Estimated by` is the name from the
`rmine whoami` you ran in preflight, `Date` is today in `YYYY-MM-DD`, and
`Confidence` is graded on how much of the estimate came from the rubric's
anchor table — see `## Confidence` there. Never emit a bare grade without the
reason next to it.

Then check it:

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/estimate/scripts/check_format.py" ./estimates/estimate-<id>.md
```

**Fix whatever it reports before telling the user you're done.** It only checks
things that are deterministically true or false — arithmetic, the points
formula, the required headers, the last-line contract. A file that fails it
drops out of the calibration corpus silently, which is the one failure nobody
notices until `/calibrate` returns less than it should.

**Tell the user to commit it.** That directory is the team's estimate corpus
and the only input `/calibrate` has. `/calibrate` needs 20+ tickets before its
own bar for acting on a result is met, and an uncommitted file on one laptop
never reaches it. An estimate that isn't committed is an estimate the team
can't learn from.

Include a short **Assumptions** block, placed **above `Breakdown:`** so the
total stays last. Assumptions change how the number should be read, and a
reader who doesn't see them will over-trust it:

- whether the estimate assumes AI-assisted development
- which linked tickets were treated as shipped foundations vs dependencies
- anything the auditor flagged non-blocking that you priced into Discussions
- which parts you're least confident in
- any line item priced with no close match in the rubric's anchor table — those
  are the estimator's judgment rather than the team's calibration, and deserve
  less trust than the rest of the number

## Calibration

Everything the estimate is priced against lives in
`${CLAUDE_PLUGIN_ROOT}/skills/estimate/references/rubric.md`, which ships with
the plugin. There is nothing for a new team member to set up, and no local file
to populate — install the plugin and the calibration is the same one everyone
else is using.

That is deliberate. A shared rubric edited through PRs means the whole team is
wrong in the same direction, which `/calibrate` can measure and correct. Per
person calibration files drift apart silently and can't be measured at all.

The anchors were derived from real estimates against this product, but from
**estimates rather than outcomes** — see `## Known bias` in the rubric. Run
`/calibrate` against the committed `estimates/` directory to measure them
against hours actually logged; it will tell you when there's enough signal to
change anything, and default to changing nothing until then.
