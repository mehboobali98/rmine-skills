# Scene script

The JSON file `run.mjs` replays. Rehearsal writes it, recording replays it
unchanged, so what was rehearsed is what gets filmed.

```json
{
  "issue": 123,
  "subject": "Ticket subject",
  "mode": "video",
  "viewport": { "width": 1280, "height": 800 },
  "hide": [".dev-toolbar", "#chat-widget"],
  "omitted": [{ "criterion": "Bulk export", "reason": "needs the search index running" }],
  "scenes": [
    {
      "caption": "Filter the list by status",
      "criterion": "The acceptance criterion this scene proves",
      "start": "/items",
      "steps": [
        { "click": { "role": "button", "name": "Filters" } },
        { "select": { "label": "Status" }, "value": "Open" }
      ],
      "expect": [{ "visible": { "text": "3 results" } }, { "url": "status=open" }]
    },
    {
      "caption": "Clear the filter",
      "steps": [{ "click": { "role": "button", "name": "Clear" } }],
      "expect": [{ "visible": { "text": "12 results" } }]
    }
  ]
}
```

## Fields

| Field | Meaning |
|---|---|
| `mode` | `video`, or `screenshots` (one image per scene) |
| `viewport` | Page size in CSS pixels. 1280x800 keeps text readable when the video plays scaled down |
| `hide` | CSS selectors hidden while filming: dev toolbars, profilers, chat and help widgets. Only things unrelated to the feature |
| `omitted` | Criteria the take can't show, each with the reason. The comment lists them as `Not shown: ...` |
| `caption` | One line a PM would say, naming what to notice, in about 60 characters. It shows below the video, in a frame with the step, a progress bar and the time, so it never covers the app |
| `criterion` | The acceptance criterion the scene proves; kept in the chapter file |
| `start` | A path on the saved URL. Required on scene 1. A later scene without it carries on from where the previous one ended |
| `steps` | What to do, in order |
| `expect` | Checks that must pass at the end of the scene. A failed check stops the take |

## Locators

Exactly one of `role` (with an optional `name`), `label`, `text`,
`placeholder`, `testId` or `css`, in that order of preference: `css` breaks
first when the markup changes. Names and text match as substrings; add
`"exact": true` when one name contains another ("1U" and "10U").

A control with no accessible name needs `css`. Playwright's selector
extensions work there: `:has-text('Half')`, `:text-is('16')`,
`button:left-of(:text('Save'))`, `>> nth=0`.

## Steps

| Step | Shape |
|---|---|
| `goto` | `{ "goto": "/path" }` |
| `click`, `hover` | `{ "click": <locator> }` |
| `fill`, `select` | `{ "fill": <locator>, "value": "text" }` |
| `drag` | `{ "drag": <locator>, "to": <locator> }`, for drag and drop and drawn connections |
| `press` | `{ "press": "Enter" }` |
| `wait` | `{ "wait": 1000 }`, only when nothing on screen can be waited for |

## Checks

`visible` and `hidden` take a locator; `text` is a substring anywhere on the
page; `url` is part of the address. A check proves the criterion: "the saved
row shows Open" is a check, "the Save button exists" is not.

## A take worth watching

Watchers give the video a minute between other work. Every second should show
the feature.

- **One story, one take.** Order the scenes so each builds on the last, and
  leave `start` off every scene after the first that stays on the same page.
  Each `start` is a reload the viewer sits through.
- **Start where the criterion happens.** Open the page itself, not a menu that
  leads to it.
- **Clear what the last scene left open.** A selection or panel from one scene
  can cover the next scene's target. Click something that resets it, such as
  another element on the canvas.
- **Show the change, then hold.** Each scene ends on its checked state, held
  long enough to read. The contact sheet shows that frame per scene; if a frame
  doesn't make the criterion obvious, the scene needs a better ending.
- **Captions name the outcome**, in a PM's words, short enough for one line.
- **Leave data as you found it.** Scenes change things on screen without
  saving, unless saving is the criterion.

A visible password field stops the run, because that is how a sign-in page is
recognised. A criterion whose own screen has one (a change-password form)
goes in `omitted`.
