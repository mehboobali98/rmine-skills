---
name: demo
description: Record a demo of a finished feature in the developer's locally running app, one scene per acceptance criterion, and post the video (or screenshots) with a chapter list as one Redmine comment after explicit approval. Use when the user asks to demo a ticket, record a feature walkthrough, show PM or QA a feature, or replace a demo meeting with a video on the ticket.
---

# Demo

A finished feature usually waits for a demo meeting before QA gets it. This
skill replaces the meeting. You drive the developer's local app through the
ticket's acceptance criteria, record one clean take, and post it to the ticket
with a chapter list. PM and QA watch it when they are free and reply against a
time: "at 1:30 the empty state is wrong".

PM and QA need to see the real feature in the real app. Plain footage, one
caption per scene, a chapter list. No title cards, zooms or music.

**Never post a demo that hides a bug.** Every scene has a check. If a check
fails while recording, the run stops, the video is deleted, and nothing is
posted. Report what was on screen instead.

**This skill drives the browser and nothing else.** It never starts a server,
touches a database, seeds data, or handles a password. If a scene needs data
that isn't there, the developer creates it.

**It writes one comment to Redmine, only after an explicit yes** for that exact
text and those files, in this run, on this ticket. Nothing else changes: no
status, no fields, no assignee. Step 6 has the rules.

`$S` below is `${CLAUDE_PLUGIN_ROOT}/skills/demo/scripts`.

## 0. Preflight

```sh
rmine whoami
rmine version
node -v
ffmpeg -version | head -1
```

- `rmine whoami` fails: stop and point at
  `go install github.com/mehboobali98/rmine/cmd/rmine@latest` then
  `rmine config init`.
- Step 6 needs rmine v0.7.0 or later for `--file`. Say so now if it is older.
- Node 18 or later, and `ffmpeg` with `ffprobe` on `PATH`.
- If `${CLAUDE_PLUGIN_ROOT}/node_modules/playwright` is missing (the first run,
  or after a plugin update), install it:

  ```sh
  npm install --prefix "${CLAUDE_PLUGIN_ROOT}"
  npx --prefix "${CLAUDE_PLUGIN_ROOT}" playwright install chromium
  ```

Run from inside the product repo. Settings, the saved session and every output
file live outside it, per user and per repo:

```sh
REPO=$(basename "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")")
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/rmine-skills/demo/$REPO"
node "$S/session.mjs" check "$STATE"
```

| Exit | Meaning | Do |
|---|---|---|
| 0 | Signed in | Go to step 2 |
| 3 | The app is not reachable | Stop. Say which URL, and that the developer starts the app. Never start it yourself |
| 4 | No session, or it expired | Step 1 |

## 1. Sign in (once per machine and app)

Each developer signs in by hand with their own local account. You never see or
type a password.

1. Ask for the app's local URL if `$STATE/settings.json` has none.
2. Start the sign-in window in the background:
   `node "$S/session.mjs" signin "$STATE" <url>`.
3. Tell the developer a browser window opened, and to sign in there. Then ask
   with AskUserQuestion whether they are signed in.
4. On yes: `touch "$STATE/.signed-in"`. The script saves the session and exits
   0. Exit 4 means the page still shows a password field: ask them to finish
   and confirm again. Exit 6 means the window was closed or 15 minutes passed.

The first time, also ask for Redmine's maximum attachment size
(Administration, Settings, Files, "Maximum attachment size") and write it to
`max_attachment_mb` in `$STATE/settings.json`. If they don't know it, keep the
default of 5, Redmine's own default.

## 2. Script the scenes

Read the ticket and its spec exactly as `/estimate` step 1 does: the ticket
with `rmine issue view <id> --comments -o json`, then the Google Doc,
attachment or description, and the linked issues.

Turn each acceptance criterion into one scene: where it starts, what to do,
what must be on screen at the end (the check), and a one-line caption in plain
words a PM would use. With no acceptance criteria, draft scenes from the
description and say that you did.

Show the developer the scene list and get a yes with AskUserQuestion. Propose
the format in the same question:

- **Screenshots** when every scene ends in one static state worth seeing.
- **Video** when any scene has a flow worth watching.

The developer can override either way.

Write the scenes to `$STATE/<id>/scenes.json`:

```json
{
  "issue": 123,
  "subject": "Ticket subject",
  "mode": "video",
  "viewport": { "width": 1280, "height": 800 },
  "scenes": [
    {
      "caption": "Filter the list by status",
      "criterion": "The acceptance criterion this scene proves",
      "start": "/items",
      "steps": [
        { "click": { "role": "button", "name": "Filters" } },
        { "fill": { "label": "Status" }, "value": "Open" },
        { "press": "Enter" }
      ],
      "expect": [
        { "visible": { "text": "3 results" } },
        { "url": "status=open" }
      ]
    }
  ]
}
```

- A locator is one of `role` (with an optional `name`), `label`, `text`,
  `placeholder`, `testId` or `css`. Prefer them in that order. `css` breaks
  first when the markup changes. Names and text match as substrings; add
  `"exact": true` when one name is part of another ("1U" and "10U").
- Steps: `goto` (a path), `click`, `hover`, `fill` and `select` (each with
  `value`), `drag` (with a `to` locator, for drag and drop and drawn
  connections), `press` (a key), `wait` (milliseconds, only when nothing on
  screen can be waited for).
- Checks: `visible`, `hidden` (a locator), `text` (anywhere on the page), `url`
  (part of the address).
- `start` is a path on the saved URL, required on the first scene. A later
  scene without `start` carries on from where the previous one ended, so the
  take has no reloads between scenes; give a scene its own `start` only when
  it happens on another page. Start on the page where the criterion happens,
  not on a menu that leads there.

Any visible password field stops the run, because that is how a sign-in page
is recognised. A criterion whose own screen has one (a change-password form)
can't be filmed.

When a criterion can't be filmed (that case, or a local service the developer
chose not to start), list it in the script's top-level `omitted`, as
`{ "criterion": "...", "reason": "..." }`. The comment then says
`Not shown: <criterion> (<reason>).`, so nobody reads the video as covering
it.

A check must prove the criterion, not only that the page loaded. "The saved
row shows the new status" is a check; "the Save button exists" is not.

## 3. Rehearse, then record

Work out the exact steps against the live app first, unrecorded. Recording you
while you explore would capture every pause and wrong turn.

```sh
node "$S/run.mjs" rehearse "$OUT/scenes.json" "$STATE" "$OUT"
node "$S/run.mjs" rehearse "$OUT/scenes.json" "$STATE" "$OUT" --scene 2 --steps 1
```

where `OUT="$STATE/<id>"`. Each run prints `PASS`, `FAIL` or `STOPPED` per
scene and leaves `look.png` and `look.aria.txt` (the page's accessibility
tree) from where it stopped. Read both to find the next locator. On a failure
the same pair is written as `failure.png` and `failure.aria.txt`.

When every scene passes, record the script in one take:

```sh
node "$S/run.mjs" record "$OUT/scenes.json" "$STATE" "$OUT"
node "$S/run.mjs" screenshots "$OUT/scenes.json" "$STATE" "$OUT"
```

| Exit | Meaning | Do |
|---|---|---|
| 0 | Every check passed | Step 4 |
| 1 | A step or check failed | Read `failure.png`. If the script was wrong (a locator, a missing wait), fix it, rehearse and record again. If the feature is wrong, stop and tell the developer which scene and what was on screen. Never loosen a check to get a take |
| 2 | The scene script is invalid | Fix what it lists |
| 4 | The app showed a sign-in page | Step 1, then record again |

A failed take deletes its video, so it can never be posted by mistake.

## 4. Assemble

```sh
node "$S/assemble.mjs" "$OUT" --subject "<ticket subject>" \
  --branch "$(git rev-parse --abbrev-ref HEAD)" --sha "$(git rev-parse --short HEAD)" \
  --limit-mb <max_attachment_mb> [--dirty]
```

Check `git status --porcelain --untracked-files=no`. If it lists files, show
them to the developer and pass `--dirty` unless they confirm every one is
generated output that doesn't change what was filmed (compiled CSS a dev
server rewrites, for example). With real code changes, the commit doesn't
describe what was filmed, and the comment says so.

Each caption in the video shows its scene number and chapter time ("2/5 ·
0:16"), the same time the comment lists, and the MP4 carries chapter markers
that QuickTime and VLC show.

It writes `demo.mp4` trimmed to the scenes, `demo-chapters.json` with each
scene's start, end, caption and check, `sheet.png` with one frame per scene,
and `comment.md`. It prints `comment:` and one `attach:` line per file to
post. In screenshots mode it attaches the scene images instead.

Exit 5 means the video can't fit the limit and stay readable. Ask the
developer with AskUserQuestion: screenshots instead (`run.mjs screenshots`,
then assemble again), or two videos on the same comment (`--parts 2`). Never
post a video too blurry to read.

## 5. Review

Read `sheet.png` yourself first. Look for a scene that shows the wrong state,
or a caption covering what it describes. Then show the developer:

- the video, opened with `open "$OUT/demo.mp4"` (or the screenshots),
- `sheet.png`,
- the exact contents of `comment.md`.

Nothing is posted yet.

## 6. Post, only after an explicit yes

```sh
rmine issue comment <id> --file "$OUT/comment.md" --attach "$OUT/demo.mp4"
```

Repeat `--attach` for each `attach:` line from step 4. Never pass the comment
inline: the shell rewrites quotes and `$` before rmine sees them, and what
lands on the ticket is no longer the text that was approved.

The rules are the same as `/spec-interview` step 6:

- **Ask with AskUserQuestion**, after the developer has seen the video and the
  exact comment. Silence or "looks fine so far" is not a yes.
- **A general instruction is not approval.** "Demo 123 and post it" authorises
  the run, not a comment and video that didn't exist when it was said.
- **A yes doesn't carry** to another ticket, a second comment, a re-recorded
  take or a reworded comment. Change anything and ask again.
- **If you can't ask, you can't post.** In a non-interactive run, stop after
  step 5 and say it was not posted and why.

If the developer declines, tell them where the files are. They can post them
themselves.

## 7. Report

Say what was posted and on which ticket, or that nothing was. The files stay in
`$OUT`: `demo.mp4` and `demo-chapters.json` are what a later voice-over pass
builds on.
