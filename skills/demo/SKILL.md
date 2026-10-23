---
name: demo
description: Record a finished feature in the developer's locally running app, one scene per acceptance criterion, and post the video or screenshots with a chapter list as one Redmine comment after approval. Use when the user asks to demo a ticket, record a walkthrough for PM or QA, or replace a demo meeting with a video on the ticket.
---

# Demo

A finished feature waits for a demo meeting before QA gets it. This skill
replaces the meeting: drive the developer's local app through the ticket's
acceptance criteria, film one take, and post it with a chapter list so PM and
QA can reply against a time ("at 1:30 the empty state is wrong").

The take is real footage of the real app, and every scene ends on a check. A
failed check stops the run and deletes the video, so a demo only ever shows a
feature that works.

The skill works through the browser alone. Servers, data and sign-in belong to
the developer: they start the app, create any data a scene needs, and type
their own password. The only write to Redmine is one comment, posted after an
explicit yes (step 6).

`$S` is `${CLAUDE_PLUGIN_ROOT}/skills/demo/scripts`. Run from inside the
product repo.

## 0. Preflight

```sh
rmine whoami && rmine version && node -v && ffmpeg -version | head -1
```

`rmine` v0.7.0 or later (if missing: `go install
github.com/mehboobali98/rmine/cmd/rmine@latest`, then `rmine config init`),
Node 18 or later, `ffmpeg` and `ffprobe`. If
`${CLAUDE_PLUGIN_ROOT}/node_modules/playwright` is missing, install it:

```sh
npm install --prefix "${CLAUDE_PLUGIN_ROOT}"
npx --prefix "${CLAUDE_PLUGIN_ROOT}" playwright install chromium
```

Settings, the session and all output live per user and per repo, outside the
repo:

```sh
REPO=$(basename "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")")
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/rmine-skills/demo/$REPO"
OUT="$STATE/<id>"
node "$S/session.mjs" check "$STATE"
```

Exit 0: go to step 2. Exit 4: step 1. Exit 3: the app isn't reachable at the
printed URL; ask the developer to start it, and stop.

## 1. Sign in (once per machine and app)

1. Ask for the app's local URL, and for Redmine's maximum attachment size
   (Administration, Settings, Files; 5 MB if they don't know).
2. Run `node "$S/session.mjs" signin "$STATE" <url>` in the background. A
   browser window opens; the developer signs in there.
3. Ask with AskUserQuestion whether they are signed in. On yes, `touch
   "$STATE/.signed-in"`.
4. Set `max_attachment_mb` in `$STATE/settings.json`.

Done when `session.mjs check` exits 0. (Exit 4 from `signin`: a password field
is still showing. Exit 6: the window closed or 15 minutes passed.)

## 2. Script the scenes

Read the ticket and its spec the way `/estimate` step 1 does:
`rmine issue view <id> --comments -o json`, then the Google Doc, attachment or
description, and linked issues.

Draft one scene per acceptance criterion, each with a caption and a check that
proves it. With no acceptance criteria, draft from the description and say so.
Propose **video** when any scene has a flow worth watching, **screenshots**
when every scene ends in one static state.

Read `references/scene-script.md` before writing `$OUT/scenes.json`: the
format, and what makes a take worth the watchers' time.

Done when the developer has approved the scene list and the format with
AskUserQuestion, and any criterion that can't be filmed is in `omitted` with
its reason.

## 3. Rehearse, then record

Rehearse unrecorded until every scene passes. Each run prints `PASS`, `FAIL` or
`STOPPED` per scene and leaves `look.png` and `look.aria.txt` (the page's
accessibility tree) from where it stopped; read both to find the next locator.
`--scene N --steps K` stops partway through a scene, after running the scenes
it carries on from.

```sh
node "$S/run.mjs" rehearse "$OUT/scenes.json" "$STATE" "$OUT" [--scene N --steps K]
node "$S/run.mjs" record "$OUT/scenes.json" "$STATE" "$OUT"        # or: screenshots
```

| Exit | Do |
|---|---|
| 0 | Step 4 |
| 1 | Read `failure.png` and `failure.aria.txt`. A wrong locator or timing is a script fix: fix, rehearse, record again. A feature that misbehaves is a finding: stop, and tell the developer which scene and what was on screen. Checks stay as strict as the criterion |
| 2 | Fix the script errors it lists |
| 4 | The app showed a sign-in page: step 1, then record again |

Done when `record` (or `screenshots`) exits 0.

## 4. Assemble

Run `git status --porcelain --untracked-files=no`. If it lists files, show
them to the developer: pass `--dirty` unless every one is generated output
that doesn't change what was filmed (compiled CSS a dev server rewrites).

```sh
node "$S/assemble.mjs" "$OUT" --subject "<ticket subject>" \
  --branch "$(git rev-parse --abbrev-ref HEAD)" --sha "$(git rev-parse --short HEAD)" \
  --limit-mb <max_attachment_mb> [--dirty] [--parts 2]
```

It cuts page loads out of the take, encodes `demo.mp4` with chapter markers to
fit the limit, and writes `sheet.png` (each scene's final frame),
`demo-chapters.json` and `comment.md`. It prints `comment:` and one `attach:`
line per file.

Exit 5: the video can't fit the limit and stay readable. Ask the developer
with AskUserQuestion: screenshots instead, or `--parts 2` for two videos on
the comment.

## 5. Review

Read `sheet.png` first. Each frame should show its scene's criterion plainly,
with the caption clear of what it describes; re-script any scene whose frame
doesn't. Then `open "$OUT/demo.mp4"` for the developer and show `sheet.png`
and the exact text of `comment.md`.

Done when the developer has seen all three.

## 6. Post, after an explicit yes

```sh
rmine issue comment <id> --file "$OUT/comment.md" --attach "$OUT/demo.mp4"
```

Repeat `--attach` for each `attach:` line. Post the file that was shown: text
passed inline gets rewritten by the shell.

The approval rules are `/spec-interview` step 6's:

- **Ask with AskUserQuestion** after the developer has seen the video and the
  comment. Only a chosen yes counts.
- **The yes covers this comment and these files.** "Demo 123 and post it"
  authorises the run; the comment it produced still needs its own yes.
- **A yes is single-use.** Another ticket, a second comment, a new take or a
  reworded comment each need a fresh one.
- **No prompt, no post.** In a non-interactive run, stop after step 5 and say
  it wasn't posted and why.

If they decline, tell them where the files are.

## 7. Report

Say what was posted and where, or that nothing was. `demo.mp4` and
`demo-chapters.json` stay in `$OUT` for a later voice-over pass.
