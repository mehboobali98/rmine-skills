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
   python3 <skill-dir>/scripts/docx2txt.py <scratch-dir>/<file>.docx
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

**If `INCOMPLETE`:** print the blocking gaps, stop, don't estimate. The user can
override by saying so, in which case each gap becomes a stated assumption and
the `Discussions` line widens.

**If it returned `WORTH ASKING` items:** ask them with AskUserQuestion *before*
estimating, batched, at most three. A gap a tech lead closes in one sentence is
worth 30 seconds of their attention and can move a line item 3x. Anything the
codebase can answer, let the estimator answer by reading code — don't spend the
user's attention on it.

## 3. Estimator

Launch the **`effort-estimator`** agent from the repo the work lands in. Pass it:

- the spec text
- the path to `references/rubric.md`
- the path to `references/samples.local.md` if it exists — if it doesn't, say so
  in the final output, because calibration is materially weaker without it
- any answers you got from the `WORTH ASKING` questions

Its definition already covers grepping before pricing, the calibration order,
and the output format. Don't re-explain them.

## 4. Validator

Launch the **`estimate-validator`** agent with the spec and the finished
estimate **only**.

**Never pass the estimator's reasoning, greps, or intermediate notes.** This is
the one check in the pipeline that isn't anchored to how the estimate was
derived, and that property exists only as long as you don't hand it the
derivation. Its own definition tells it to report the leak if you do — take that
as a real failure, not a formality.

## 5. Reconcile and write

Apply the validator's findings. Where you disagree with it, say why in one
line rather than silently dropping it.

Print the breakdown, then write it to `./estimate-<id>.md`. Keep the format in
`rubric.md` exactly — `Total (Z hrs ~ P points)` is the literal last line so a
later estimate-vs-actual pass can parse a directory of these without guessing.

Include a short **Assumptions** block, placed **above `Breakdown:`** so the
total stays last. Assumptions change how the number should be read, and a
reader who doesn't see them will over-trust it:

- that the estimate assumes AI-assisted development (or doesn't, if the rubric
  section was turned off)
- which linked tickets were treated as shipped foundations vs dependencies
- anything the auditor flagged non-blocking that you priced into Discussions
- which parts you're least confident in
- whether `samples.local.md` was available — without it, calibration is
  materially weaker and the number deserves less trust

## Setup

`samples.local.md` is gitignored and absent on a fresh clone. Without it the
skill runs on `rubric.md` alone. To populate it, extract your own past
estimates into `references/samples.local.md` — the closest comparable sample
outweighs any calibration table.
