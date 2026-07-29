---
name: estimate
description: Turn a Redmine ticket into a frontend/backend effort estimate in hours and points, via a spec-completeness gate, a codebase-aware estimator, and an independent validator. Use when the user asks to estimate a ticket, scope a spec, break down effort, produce an ETA, or asks "how long will <issue> take". Run from inside the product repo being estimated.
---

# Estimate

Given a Redmine issue, produce the house-format effort breakdown. Three agents:
an **auditor** that refuses to estimate an unusable spec, an **estimator** that
reads the actual codebase, and a **validator** that never sees the estimator's
reasoning.

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

Launch one **Explore** agent. Give it the spec text and nothing else: no
rubric, no codebase, no instruction to estimate. It must not be primed to
produce hours.

Ask it to report `READY` or `INCOMPLETE`, checking for:

- a Figma or design link, when the work implies frontend
- acceptance criteria or explicit expected behaviour
- which modules and products are affected
- API contracts for new endpoints
- data model changes stated, or explicitly none
- permissions / role impact
- migration or backfill for existing tenants
- an out-of-scope statement
- dependencies on other tickets

**The bar for blocking.** Every spec is incomplete in some way. A gate that
fires on every run gets ignored, so block only on a gap that would *materially
move the hours*:

- frontend-heavy work with no design link
- a data model change implied but never stated
- a hard dependency on unshipped work
- scope so open-ended that the total could double

Cap it at **three** blocking gaps. Everything else — no out-of-scope section,
thin acceptance criteria on a small task — is non-blocking: carry it into the
estimate's `Discussions + Additional cases` line with the gap named.

If `INCOMPLETE`: print the blocking gaps, stop, and don't estimate. The user
can override by saying so, in which case the estimate carries each gap as a
stated assumption and a widened Discussions line.

### Ask, don't just annotate

A gap that the user could close in one sentence is worth **asking about before
estimating**, not footnoting after. Use AskUserQuestion for anything that meets
all three:

- it materially moves the hours
- the user plausibly knows the answer off the top of their head
- the codebase can't settle it

The commonest example by far: *is there an existing service/pattern this can
reuse, or is it built from scratch?* That single question routinely swings a
line item 3x, and it's the kind of thing a tech lead answers instantly and a
grep answers ambiguously.

Cap it at three questions and ask them in one batch. Anything the codebase can
answer, answer by reading the codebase — don't spend the user's attention on it.

## 3. Estimator

Launch one **general-purpose** agent in the current repo. Give it the spec,
`references/rubric.md`, and `references/samples.local.md` if it exists (if it
doesn't, say so in the final output — calibration is materially weaker).

Tell it explicitly to **grep the codebase before pricing anything**: find the
real services, models, tables and existing patterns the work touches. A line
item that can't name what it touches is a line item that isn't understood.
Whether an existing pattern covers the work is the single biggest lever on the
number — resolve it by reading code, not by assuming.

Pass on the rubric's **AI-assisted development** section: the estimate assumes
the team codes with an assistant, which moves pattern-following work to the
bottom of its anchor range and leaves judgment, integration and coordination
work unchanged.

Output is the format in `rubric.md`, nothing else.

## 4. Validator

Launch one **general-purpose** agent with the spec and the finished estimate
**only**. Never pass the estimator's reasoning, its greps, or its intermediate
notes — the whole value of this pass is that it hasn't been anchored. State
this constraint when you launch it, or the reasoning will leak in.

It checks:

- arithmetic: line items sum to their section, sections sum to the total
- `points = round(hours / 4)`
- recurring items missing entirely — migration, rake backfill for existing
  tenants, ability/permissions, serializer, list view preference, redux slice,
  search integration
- line items priced against the closest comparable sample
- scope present in the spec with no line item at all
- line items too vague to be real work
- work owned by a linked ticket, priced here as well — the same hours estimated
  twice across two tickets
- AI compression applied to work that doesn't compress: demo, PR review, the
  Discussions buffer, and anything without an established in-repo pattern

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
