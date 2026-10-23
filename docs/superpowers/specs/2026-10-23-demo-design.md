# `/demo <issue>`: record a feature demo and post it to the ticket

Status: design, not built. Implementation happens in its own session from
this document.

## Why

A finished feature waits for an in-person demo before it goes to QA. PM and
QA watch it, the developer fixes their feedback, and only then does QA get the
ticket. Getting everyone in one room causes delays. Small features skip the
demo and get screenshots instead.

`/demo` removes the meeting. An agent drives the app through the ticket's
acceptance criteria, records it, and posts the video to the Redmine ticket
with a chapter list. PM and QA watch when they are free and give feedback
against a time ("at 1:30 the empty state is wrong").

## Who

- **The developer** runs it, from inside the product repo, with the app
  running on their own machine.
- **PM and QA** watch it on the ticket. They need to see the real feature in
  the real app. A polished but recreated video is worse than plain footage.

## Goals

1. A video of the real app, recorded by an agent, one scene per acceptance
   criterion, with a one-line caption on screen for each scene.
2. A Redmine comment carrying the video and a chapter list, so feedback can
   point at a time.
3. For a small feature, screenshots (one per scene) in place of a video, in the
   same comment shape.
4. The video and its chapter times left on disk, so a later voice-over skill
   can build on them.

## Non-goals (for now)

- **Voice-over and narration.** A separate, later skill. It will take this
  skill's video and chapter file as input, likely using HyperFrames.
- **Staging.** The first version records the developer's local app only.
- **Changing the ticket.** The skill adds one comment. It never changes status,
  assignee or any field.
- **Polish.** No title cards, zooms or music. Real footage, captions, chapters.

## Anti-goals (a failure even if it works)

- **A demo that hides a bug.** If a scene doesn't show what it should, the skill
  stops and says so. It never posts a video of a failing scene as if it passed.
- **A password or login screen in the video.** Recording only ever starts in a
  browser that is already signed in.
- **Posting without approval.** Same rule as `/spec-interview` step 6: the user
  sees the exact comment and the video, and says yes, in this run, for this
  ticket.
- **Company details in the plugin.** rmine-skills is public. URLs, accounts and
  anything product-specific live on the developer's machine, never in the
  plugin.
- **Touching data.** The skill drives the browser only. It never writes to the
  database or seeds test data. Missing data is the developer's to create.

## Flow

### 0. Preflight

- `rmine whoami`, exactly as `/estimate` does. `rmine issue comment --attach`
  needs rmine v0.6.0; the README already requires v0.7.0.
- Node 18+ and ffmpeg on `PATH`.
- First run on a machine: install Playwright and Chromium into the plugin
  folder, following clip-studio's precedent
  (`npm install --prefix ${CLAUDE_PLUGIN_ROOT}`, then
  `npx --prefix ${CLAUDE_PLUGIN_ROOT} playwright install chromium`).
- The app is reachable at the saved URL. The skill never starts servers; every
  product starts differently. If the app is down, say so and stop.

### 1. Sign in (once per machine and app)

Every developer has their own account on their local database, so the skill
never handles credentials.

- The first time, ask for the app's local URL, open a visible browser on it,
  and ask the developer to sign in by hand. Once signed in, save the session
  (Playwright `storageState`) and the URL to a per-user directory outside the
  repo, readable only by the user.
- Later runs reuse it. If the session has expired, open the window again and
  ask the developer to sign in.

### 2. Script

Read the ticket with `rmine issue view <id> --comments -o json`, and the spec
the same way `/estimate` step 1 finds it. Turn each acceptance criterion into a
scene: where to start, what to do, what must be visible at the end (the
check), and a one-line caption. With no acceptance criteria, draft scenes from
the description and say so.

Show the scene list to the developer and get a yes before recording. Also
propose video or screenshots here: screenshots when every scene is a single
static state, video when any scene has a flow worth watching. The developer
can override.

### 3. Rehearse, then record

Rehearse first, unrecorded: the agent works out the exact steps for each
scene against the live app, and writes them down as a fixed script. Then
record that script in one clean take. Recording the agent while it explores
would capture its pauses and wrong turns.

While recording:

- Each scene's check must pass. If one fails, stop, report which scene and what
  was on screen, and post nothing.
- Note the time each scene starts. These become the chapters.
- Show the scene's caption on screen.
- Show the mouse pointer and slow actions down enough to follow. Playwright's
  recording doesn't show the pointer by itself.

### 4. Assemble

One MP4, sized to fit Redmine's attachment limit (see open questions).
ffmpeg does the encoding. Write a chapter file next to it with each scene's
start time, caption and check.

If the video can't fit the limit at a watchable quality, say so and offer
two ways out: screenshots in its place, or splitting the scenes across two
videos on the same comment. The developer picks. Never post a video too
blurry to read.

### 5. Review

Show the developer the video, or a contact sheet of one frame per scene, plus
the exact comment text. Nothing is posted yet.

### 6. Post

Only after an explicit yes from AskUserQuestion, same rules as
`/spec-interview` step 6. Write the comment to a file and post that file with
the video:

```sh
rmine issue comment <id> --file <comment-file> --attach <demo.mp4>
```

The comment, plain lines that read the same in Markdown and Textile:

```
Demo of <ticket subject>, recorded on <branch> at <short sha>.

0:00 <scene 1 caption>
0:42 <scene 2 caption>
1:30 <scene 3 caption>

Reply with a time and what's wrong, and I'll pick it up before QA.
```

## Decided by the user

- Agent-driven recording, not the developer recording their own screen.
- Playwright only for this skill. HyperFrames and clip-studio both render
  videos from HTML made to be filmed, not from a running app; they fit the
  later voice-over and polish work, not this one.
- Plain footage with captions and a chapter list is enough for PM and QA.
- Local dev machines first. Staging later.
- Each developer signs in with their own local account.
- Only a comment. No status or assignee change.

## Calls made in this design (check these)

1. The skill is `/demo <issue>`, in rmine-skills, because it reads and writes
   Redmine tickets.
2. Sign-in by hand once, then a saved session per user, outside the repo.
3. Scenes come from acceptance criteria, approved before recording.
4. Rehearse unrecorded, then record a fixed script in one take.
5. A failing scene stops the run. Nothing is posted.
6. Screenshots vs video is proposed at the script step, the developer decides.
7. The comment names the branch and commit recorded, so QA knows what they
   watched.
8. Output (video, chapter file, screenshots, the scene script) lives in a
   per-user directory keyed by repo and ticket, not in the product repo, so
   videos never get committed by accident.
9. A video too big for the attachment limit falls back to screenshots or a
   split, chosen by the developer.
10. This adds the plugin's first Node dependency. The README's "stdlib only,
   nothing to install" line changes for `/demo`.

## Left to the builder

- Captions: drawn into the page during recording, or added by ffmpeg
  afterwards. Drawing them in the page needs nothing extra from ffmpeg and
  keeps timing exact.
- Viewport size, pace of actions, encoding settings.
- The format of the rehearsed scene script, and of the chapter file.
- Tests for the scripts, wired into CI next to the Python suites.

## Open questions

1. **Redmine's attachment size limit.** Redmine's default is 5 MB, and a few
   minutes of video can exceed it. The skill needs the real limit to size the
   encode, or to fall back to screenshots. Found under Administration,
   Settings, Files, "Maximum attachment size".
