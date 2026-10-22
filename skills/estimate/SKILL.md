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
answer the spec's open items from code and write a change plan, and reconcile
the validator's findings. **Their prompts live in their own
definitions — don't paraphrase them here**, or the constraints degrade with
every relay.

Run this from inside the repo the work will land in. Without the codebase the
estimate degrades to generic guesswork — say so plainly rather than pretending
otherwise. Work that lands in a second repo, such as a fork or a sibling app,
is read in step 3.

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
- **The mode: `agent-driven` or `hand-written`.** The default is agent-driven:
  an agent writes the code, and the developer plans, steers, reviews, tests and
  demos. Use hand-written only when the user says the work will be typed by
  hand. If they haven't said, use agent-driven — don't ask, but always write it
  in the `Mode:` header, because the same ticket can price more than twice apart
  between the two.

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

It returns `READY` or `INCOMPLETE`, plus blocking gaps, non-blocking gaps,
anything `WORTH ASKING`, and the `OPEN ITEMS` the spec leaves to the developer.
Step 3 works through those.

**If `INCOMPLETE`:** print the blocking gaps, stop, don't estimate. The right
next move is fixing the spec rather than estimating it anyway — point at
`/spec-interview <id>`, which ships with this plugin, runs the same auditor, and
writes the answers back to the ticket. The user can also override by saying so,
in which case each gap becomes a stated assumption, the `Discussions` line
widens, and `Confidence` drops to `Low`.

**If it returned `WORTH ASKING` items:** ask them with AskUserQuestion *before*
estimating, batched, at most three. A gap a tech lead closes in one sentence is
worth 30 seconds of their attention and can move a line item 3x. Anything the
codebase can answer, answer in step 3 by reading code. Don't spend the
user's attention on it.

Each item arrives as a `Q:`/`A:` pair. **Put the auditor's recommended answer
first, labelled `(Recommended)`.** That turns "do my thinking for me" into
"correct me if I'm wrong" — much cheaper to answer, and it means a user who
skips the question still gets a stated assumption rather than a silent one.
Whatever they don't answer, carry the recommendation into `Assumptions:`.

## 3. Feasibility and plan

Specs leave some questions to the developer: "dev to confirm", "TBA", "check
whether X already works". Priced as they stand, each one becomes a risk the
estimator pays for, and work in a repo it never reads gets priced as a black
box. Both run high, and both can pick the wrong design. So before anything is
priced, answer what the code can answer and write down what will change.

Make a scratch directory **outside the product repo** and write the combined
spec text to `spec.md` in it. Then:

1. **List the open items and the repos.** Start from the auditor's
   `OPEN ITEMS`, then add any spec item marked "dev to confirm", "dev to
   verify", "TBA" or similar that it missed. List every repo the work lands
   in: this one, plus any fork, sibling app or embedded server the spec or the
   code names. A repo that isn't checked out gets cloned read-only into the
   scratch directory:

   ```sh
   git clone --depth 1 <url> <scratch-dir>/repos/<name>
   ```

   The clone is there to read. Never install, build or run anything from it.
   If a repo can't be reached, say so, and every item in it stays unverified.

2. **Answer each open item from code.** Either an answer with a `file:line`
   from the repo that holds it, or `unverified` and the test that would settle
   it, such as "one session on a real device". Read the repo that owns the
   behaviour. A comment in this repo about what a server can do is a claim;
   the server's own code is the answer.

3. **Write one plan entry per spec item.** The files or modules touched, the
   approach, and the existing pattern it follows, one or two lines each. An
   item that spans backend and frontend gets one entry per layer. An item the
   code shows already works still gets an entry, since someone has to check
   it. Save it as `plan.md` next to `spec.md`:

   ```markdown
   # Plan: <issue id> <subject>

   ## Repos
   - <name>: <local path> (<what changes there>)

   ## Open items
   1. <the item, as the spec words it>
      Answer: <answer> (`<repo>/<file>:<line>`)
   2. <the item>
      Answer: unverified. Settled by: <the test>

   ## Plan
   1. <spec item>
      Repo: <name>
      Files: `<file>`, `<file>`
      Approach: <one or two lines>
      Pattern: <the existing code it follows, `file:line`, or "none found">
      Depends on: open item 2
   ```

   `Depends on` appears only when the entry rests on an open item. The
   validator uses it to find the lines an `unverified` answer puts at risk.

   No hours in the plan. Pricing is the estimator's job, and a number here
   anchors it.

Don't ask the user what this step can answer from code. An item that only a
person can settle stays `unverified`, and the estimate carries it.

## 4. Estimator

Launch the **`effort-estimator`** agent from the repo the work lands in. Pass it:

- the spec text
- the path to `plan.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/estimate/references/rubric.md` — the format and
  the calibration anchors
- `${CLAUDE_PLUGIN_ROOT}/skills/estimate/references/format-examples.md` — two
  worked estimates showing the shape and the level of specificity. **Their
  numbers are invented**; say so when you pass the path, so nothing anchors to
  them
- the mode, `agent-driven` or `hand-written`
- any answers you got from the `WORTH ASKING` questions

Its definition already covers grepping before pricing, pricing the plan,
pricing against the anchor table, and the output format. Don't re-explain them.

## 5. Validator

Write the finished estimate to `estimate.md` in the same scratch directory as
`spec.md` and `plan.md`, **not the product repo**. They are pipeline
intermediates, and committing them would pollute the estimate corpus. Then
launch the **`estimate-validator`** agent with **nothing in its prompt but
those three paths**.

Passing paths rather than inline content is the whole discipline here. Inline
content invites summarising, and summarising is how the estimator's reasoning
leaks in — at which point this stops being an independent check and becomes an
expensive agreement. Three paths and a sentence naming which is which.

The plan is not the estimator's reasoning. It was written before the estimator
ran, and the estimate is meant to price it, so the validator needs it to check
that every entry got a line. **Never pass the estimator's reasoning, greps, or
intermediate notes**, in any form. Its definition tells it to report the leak
if you do; treat that as a real failure, not a formality.

## 6. Reconcile and write

Apply the validator's findings. Where you disagree with it, say why in one
line rather than silently dropping it.

Print the breakdown, then write it to `./estimates/estimate-<id>.md` in the
product repo, creating the directory if it doesn't exist. Keep the format in
`rubric.md` exactly — `Total (Z hrs ~ P points)` is the literal last line so a
later estimate-vs-actual pass can parse a directory of these without guessing.

Fill the header from what you already have: `Estimated by` is the name from the
`rmine whoami` you ran in preflight, `Date` is today in `YYYY-MM-DD`,
`Confidence` is graded on how much of the estimate came from the rubric's
anchor table — see `## Confidence` there — and `Mode` is the one you settled in
preflight. Never emit a bare grade without the reason next to it. An
agent-driven estimate also keeps the estimator's `Range:` line; if reconciling
the validator moved the Total, move the range with it.

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

- in agent-driven mode, any line priced above its agent-driven anchor row and
  the reason, and the lines that set the top of the `Range:`
- which linked tickets were treated as shipped foundations vs dependencies
- each `unverified` answer from the plan that a line depends on, and the test
  that would settle it
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
