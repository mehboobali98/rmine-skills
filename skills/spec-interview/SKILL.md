---
name: spec-interview
description: Turn a spec's gaps into answered questions — audit it, route each gap to whoever can actually close it, and write the answers back to the ticket. Use when a spec is too vague to estimate, when /estimate returns INCOMPLETE, or when the user asks to grill, interrogate, tighten, or fill in a spec before work starts.
---

# Spec interview

`/estimate` refuses to price a spec it can't read, and then hands you an
`INCOMPLETE` verdict with nowhere to take it. This is where it goes.

Audit the spec, turn the gaps that matter into questions, answer the ones that
can be answered here, and **write the rest back to the ticket** — so the spec is
fixed where it lives rather than in one person's terminal.

**This skill writes to Redmine, and never without explicit approval.** It is
the only skill in this plugin that writes anything at all. It posts one comment,
only after showing the user the exact text and getting a yes for *that text* on
*that ticket*. Nothing else is touched: no status, no fields, no assignee. The
approval rule is unconditional and is spelled out in step 6 — read it before
running `rmine issue comment`.

## 0. Preflight

```sh
rmine whoami
```

One call covers `rmine` missing from `PATH`, no profile configured, and
credentials that don't authenticate. If it fails, stop and point at the fix —
`go install github.com/mehboobali98/rmine/cmd/rmine@latest` then
`rmine config init`.

## 1. Get the spec

Accept a Redmine URL or a bare issue ID.

```sh
rmine issue view <id> --comments -o json
```

The spec lives in one of four places — check in this order, exactly as
`/estimate` does, because an interview against half a spec asks questions the
spec already answered:

1. **A Google Docs link in the description**, read with the Google Drive tools.
   If Drive isn't authenticated, ask for the text rather than guessing.
2. **An attached document**, via `rmine issue attachments <id> --download` and
   `${CLAUDE_PLUGIN_ROOT}/skills/estimate/scripts/docx2txt.py`.
3. **The description itself**, when it's substantial prose.
4. **Nothing.** Then there is no spec to interview — the whole ticket is the
   gap. Say that plainly and ask for a description before anything else.

Pull every `issues/<id>` reference out of the description and the comments and
read those too. A question already settled in a linked ticket is a question that
makes you look like you didn't read the ticket.

Comments count as spec. A clarification agreed there is spec content, and so is
a scope change.

## 2. Audit

Launch the **`spec-auditor`** agent with the spec text **and nothing else** —
no rubric, no codebase paths, no mention of estimating. Its definition carries
the checklist and the blocking bar. Don't restate them, and don't add anything
that primes it to size the work.

It returns `READY` or `INCOMPLETE`, blocking gaps, non-blocking gaps, and
`WORTH ASKING` items as `Q:`/`A:` pairs — each question already carrying the
answer the auditor would assume.

**If it comes back `READY` with nothing worth asking, stop and say so.** A spec
that can be estimated does not need an interview, and manufacturing questions to
look thorough wastes the requester's attention on the run where you most needed
their goodwill. This is a valid and common outcome.

## 3. Route every gap before you ask anyone

Each gap has exactly one right destination. Deciding which is the whole value of
this skill — an interview that forwards every question to whoever typed the
command is a slower way of guessing.

- **Code can settle it** → settle it by reading code. Whether an existing
  service or pattern covers the work is the archetype here, and it is a grep,
  not a question. Never spend a human's attention on something the repo answers.
- **The person running this can settle it** → ask now, in step 4.
- **Only the requester can settle it** → it goes in the ticket comment. Scope
  boundaries, business rules, which customer asked and what they actually
  wanted, whether an edge case matters.

Non-blocking gaps mostly don't belong in the comment at all. They are already
priced into the `Discussions + Additional cases` line by `/estimate` with the
gap named. Including them dilutes the questions that block.

## 4. Ask what's answerable here

Use AskUserQuestion, batched, **at most three**. Put the auditor's recommended
answer first, labelled `(Recommended)`.

A bare question asks the reader to do your thinking. A question with a
recommendation attached asks them to correct you, which is far cheaper to answer
and much likelier to get a reply. Whatever goes unanswered keeps its
recommendation and travels on as a stated assumption.

## 5. Draft the comment

Write it out and **show it in full before posting**. It is going on a ticket
other people read, under the user's name.

Keep it short enough to answer in one sitting:

```
Blocking questions before this can be estimated:

1. <question>
   Assumption if we don't hear back: <the auditor's recommended answer>
2. ...

Happy to proceed on the assumptions above if that's easier than answering —
they'll be recorded on the estimate either way.
```

Rules for the comment:

- **At most three questions.** A list of nine gets no reply at all.
- **Every question carries its assumption.** That is what converts an ask into
  a confirm, and it means silence still produces a documented decision.
- **No hours, no sizing, no estimate.** The auditor is forbidden from producing
  hours and so is this. A comment that says "this looks like 3 days" has quoted
  a number nobody validated, on the public record.
- **No blame.** "The spec doesn't say X" is a gap. "The spec is incomplete" is a
  performance review.

## 6. Post — only after an explicit yes

```sh
rmine issue comment <id> "<comment text>"
```

**This command runs only after the user has seen the exact text and approved it,
in this run, for this ticket.** There is no version of this where the comment
goes up first and gets reviewed afterwards: a Redmine comment notifies every
watcher on the issue and cannot be quietly unsent. Getting it wrong is a
correction in front of the whole team, not a local mistake.

The approval has to be a real one:

- **Ask with AskUserQuestion.** The yes must be a choice the user made, not an
  inference from silence, from them not objecting, or from the run having got
  this far.
- **A general instruction is not approval of a specific comment.** "Interview
  54039 and post the questions" authorises the run — it cannot authorise text
  that didn't exist when they said it. Draft it, show it, then ask.
- **A yes does not carry.** Not to the next ticket, not to a second comment on
  the same ticket, and not to a revised draft. Reword anything and you ask again.
- **If you cannot ask, you cannot post.** In a non-interactive run, or anywhere
  a prompt can't reach a person, print the draft and say plainly that it was not
  posted and why.

If the user declines, hand them the drafted text. It is still useful pasted into
Slack, read out on a call, or put on the ticket by them — and by them is rather
the point.

## 7. Report, and say what's actually true

If anything got answered in step 4, fold those answers into the spec text and
**re-run `spec-auditor`** on it. That tells you whether the verdict flipped, and
it's cheap. Report the new verdict rather than assuming the interview worked.

Then say plainly where things stand:

- **`READY` now** → `/estimate <id>` will price it. Say so.
- **Still `INCOMPLETE`, questions posted** → the spec is not fixed yet; you are
  waiting on a person. Don't describe this as done.
- **Still `INCOMPLETE`, user wants a number anyway** → `/estimate` can override,
  in which case every unanswered recommendation becomes a stated assumption, the
  `Discussions` line widens, and `Confidence` drops to `Low`. That is a real
  option and worth naming — an estimate with honest assumptions beats a blocked
  ticket — but the reader has to be told which one they're holding.

The interview improves the corpus at its source. An estimate built on a spec
someone actually answered is worth more to `/calibrate` later than one built on
three assumptions and a shrug, and the difference shows up as the spread that
decides whether a calibration run can conclude anything at all.
