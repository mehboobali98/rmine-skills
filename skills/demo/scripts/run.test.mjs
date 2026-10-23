import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startFixture, sessionWithCookie, VALID_COOKIE } from './fixture-app.mjs';
import { formatTime, barGeometry } from './lib.mjs';

const RUN = new URL('./run.mjs', import.meta.url).pathname;

const SCRIPT = {
  issue: 1,
  subject: 'Items list',
  mode: 'video',
  viewport: { width: 1280, height: 800 },
  scenes: [
    {
      caption: 'Hide closed items',
      criterion: 'Closed items can be hidden',
      start: '/items',
      steps: [{ click: { role: 'button', name: 'Hide closed' } }],
      expect: [{ text: '8 shown' }, { hidden: { role: 'cell', name: 'Closed' } }],
    },
    {
      caption: 'Create an item',
      criterion: 'An item can be created',
      start: '/items',
      steps: [
        { click: { role: 'link', name: 'New item' } },
        { fill: { label: 'Name' }, value: 'Laptop' },
        { select: { label: 'Status' }, value: 'Closed' },
        { click: { role: 'button', name: 'Save' } },
      ],
      expect: [{ visible: { role: 'heading', name: 'Saved Laptop' } }, { url: '/items/new' }],
    },
  ],
};

let app;
let work;

before(async () => {
  app = await startFixture();
  work = fs.mkdtempSync(path.join(os.tmpdir(), 'demo-run-'));
});
after(() => app.close());

function stateDir(cookie) {
  const dir = fs.mkdtempSync(path.join(work, 'state-'));
  fs.writeFileSync(path.join(dir, 'settings.json'), JSON.stringify({ url: app.url, max_attachment_mb: 5 }));
  fs.writeFileSync(path.join(dir, 'session.json'), JSON.stringify(sessionWithCookie(cookie)));
  return dir;
}

function scriptFile(script) {
  const file = path.join(fs.mkdtempSync(path.join(work, 'script-')), 'scenes.json');
  fs.writeFileSync(file, JSON.stringify(script));
  return file;
}

function run(mode, script, { cookie = VALID_COOKIE, out = fs.mkdtempSync(path.join(work, 'out-')), extra = [] } = {}) {
  return new Promise((resolve) => {
    execFile(process.execPath, [RUN, mode, scriptFile(script), stateDir(cookie), out, ...extra], (err, stdout, stderr) => {
      resolve({ status: err ? err.code : 0, stdout, stderr, out });
    });
  });
}

const exists = (out, name) => fs.existsSync(path.join(out, name));

test('rehearse passes each scene and leaves a look at the last page', async () => {
  const r = await run('rehearse', SCRIPT);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /^PASS 1 Hide closed items$/m);
  assert.match(r.stdout, /^PASS 2 Create an item$/m);
  assert.ok(exists(r.out, 'look.png'));
  assert.match(fs.readFileSync(path.join(r.out, 'look.aria.txt'), 'utf8'), /heading "Saved Laptop"/);
});

test('rehearse can stop partway through a scene', async () => {
  const r = await run('rehearse', SCRIPT, { extra: ['--scene', '2', '--steps', '1'] });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /^STOPPED 2 Create an item after step 1$/m);
  assert.doesNotMatch(r.stdout, /PASS 1/);
  assert.match(fs.readFileSync(path.join(r.out, 'look.aria.txt'), 'utf8'), /heading "New item"/);
});

let recorded;

test('record writes the video and a chapter per scene', async () => {
  recorded = await run('record', SCRIPT);
  assert.equal(recorded.status, 0, recorded.stderr);
  assert.ok(fs.statSync(path.join(recorded.out, 'raw.webm')).size > 0);
  const chapters = JSON.parse(fs.readFileSync(path.join(recorded.out, 'chapters.json'), 'utf8'));
  assert.deepEqual(chapters.map((c) => c.caption), ['Hide closed items', 'Create an item']);
  assert.deepEqual(chapters.map((c) => c.criterion), ['Closed items can be hidden', 'An item can be created']);
  assert.ok(chapters[0].start >= 0);
  assert.ok(chapters[0].end <= chapters[1].start);
  assert.ok(chapters[1].start < chapters[1].end);
});

test('failed expect deletes the video, including an earlier take', async () => {
  const broken = structuredClone(SCRIPT);
  broken.scenes[1].expect = [{ text: 'Nothing like this' }];
  const r = await run('record', broken, { out: recorded.out });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /scene 2 \(Create an item\)/);
  assert.ok(exists(r.out, 'failure.png'));
  assert.ok(exists(r.out, 'failure.aria.txt'));
  assert.ok(!exists(r.out, 'raw.webm'));
  assert.ok(!exists(r.out, 'chapters.json'));
});

test('record stops on a password field', async () => {
  const r = await run('record', SCRIPT, { cookie: 'expired' });
  assert.equal(r.status, 4);
  assert.match(r.stderr, /sign/i);
  assert.ok(!exists(r.out, 'raw.webm'));
});

const CONTINUED = {
  ...SCRIPT,
  scenes: [
    { caption: 'Hide closed items', start: '/items', steps: [{ click: { role: 'button', name: 'Hide closed' } }], expect: [{ text: '8 shown' }] },
    { caption: 'Then open a new item', steps: [{ click: { role: 'link', name: 'New item' } }], expect: [{ url: '/items/new' }] },
  ],
};

test('a scene without a start carries on from the previous one', async () => {
  const kept = structuredClone(CONTINUED);
  kept.scenes[1] = { caption: 'The list keeps its filter', expect: [{ text: '8 shown' }] };
  const r = await run('rehearse', kept);
  assert.equal(r.status, 0, r.stderr);
});

test('rehearsing a continued scene runs the scenes it depends on first', async () => {
  const r = await run('rehearse', CONTINUED, { extra: ['--scene', '2'] });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /^PASS 1 Hide closed items$/m);
  assert.match(r.stdout, /^PASS 2 Then open a new item$/m);
});

test('record numbers each caption and shows its chapter time', async () => {
  const r = await run('record', CONTINUED);
  assert.equal(r.status, 0, r.stderr);
  const chapters = JSON.parse(fs.readFileSync(path.join(r.out, 'chapters.json'), 'utf8'));
  assert.deepEqual(chapters.map((c) => c.tag), ['1/2 · 0:00', `2/2 · ${formatTime(chapters[1].start - chapters[0].start)}`]);
});

function pngSize(file) {
  const buf = fs.readFileSync(file);
  return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
}

test('record renders a caption frame per scene around the viewport', async () => {
  const r = await run('record', CONTINUED);
  assert.equal(r.status, 0, r.stderr);
  const chapters = JSON.parse(fs.readFileSync(path.join(r.out, 'chapters.json'), 'utf8'));
  assert.deepEqual(chapters.map((c) => c.frame), ['frame-01.png', 'frame-02.png']);
  assert.deepEqual(pngSize(path.join(r.out, 'frame-01.png')), [1360, 964]);
});

test('the current step fills its progress segment as the scene plays', async () => {
  const r = await run('record', CONTINUED);
  assert.equal(r.status, 0, r.stderr);
  const done = await new Promise((resolve) => {
    execFile(process.execPath, [new URL('./assemble.mjs', import.meta.url).pathname, r.out, '--subject', 's', '--branch', 'b',
      '--sha', 'abc1234', '--limit-mb', '5'], (err, stdout, stderr) => resolve({ status: err ? err.code : 0, stderr }));
  });
  assert.equal(done.status, 0, done.stderr);
  const [first] = JSON.parse(fs.readFileSync(path.join(r.out, 'demo-chapters.json'), 'utf8'));
  const bar = barGeometry(SCRIPT.viewport, 2, 1);
  const sample = (t) => [...execFileSync('ffmpeg', ['-v', 'error', '-ss', String(t), '-i', path.join(r.out, 'demo.mp4'), '-frames:v', '1',
    '-vf', `crop=4:2:${bar.x + Math.round(bar.width * 0.6)}:${bar.y},scale=1:1`, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])];
  const early = sample(first.start + 0.2);
  const late = sample(first.end - 0.2);
  assert.ok(early[0] > 180, `60% along, early should still be grey: ${early}`);
  assert.ok(late[0] < 140 && late[2] > 180, `60% along, late should be indigo: ${late}`);
});

test('screenshots number each caption', async () => {
  const r = await run('screenshots', { ...CONTINUED, mode: 'screenshots' });
  assert.equal(r.status, 0, r.stderr);
  const chapters = JSON.parse(fs.readFileSync(path.join(r.out, 'chapters.json'), 'utf8'));
  assert.deepEqual(chapters.map((c) => c.tag), ['1/2', '2/2']);
});

test('record passes the omitted criteria on to assembly', async () => {
  const omitted = [{ criterion: 'Bulk delete', reason: 'not built yet' }];
  const r = await run('record', { ...SCRIPT, omitted });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(r.out, 'omitted.json'), 'utf8')), omitted);
});

test('screenshots writes one image per scene', async () => {
  const r = await run('screenshots', { ...SCRIPT, mode: 'screenshots' });
  assert.equal(r.status, 0, r.stderr);
  assert.ok(exists(r.out, 'scene-01.png'));
  assert.ok(exists(r.out, 'scene-02.png'));
  const chapters = JSON.parse(fs.readFileSync(path.join(r.out, 'chapters.json'), 'utf8'));
  assert.deepEqual(chapters.map((c) => c.start), [null, null]);
});

test('drag moves HTML5 draggables and pointer handles', async () => {
  const board = structuredClone(SCRIPT);
  board.scenes = [{
    caption: 'Drag a card and wire a socket',
    start: '/board',
    steps: [
      { drag: { css: '#card' }, to: { text: 'Drop zone' } },
      { drag: { css: '#handle' }, to: { css: '#socket' } },
    ],
    expect: [{ text: 'Dropped card' }, { text: 'Wired' }],
  }];
  for (const mode of ['rehearse', 'record']) {
    const r = await run(mode, board);
    assert.equal(r.status, 0, `${mode}: ${r.stderr}`);
  }
});

test('exact matches a whole name only', async () => {
  const items = structuredClone(SCRIPT);
  items.scenes = [{
    caption: 'Pick Item 1, not Item 10',
    start: '/items',
    steps: [{ click: { role: 'cell', name: 'Item 1', exact: true } }],
    expect: [{ visible: { role: 'cell', name: 'Item 1', exact: true } }],
  }];
  const r = await run('rehearse', items);
  assert.equal(r.status, 0, r.stderr);
});

test('hide keeps unrelated overlays out of the take', async () => {
  const hidden = { ...CONTINUED, hide: ['#count'], scenes: [{ caption: 'List without its counter', start: '/items', expect: [{ hidden: { css: '#count' } }] }] };
  const r = await run('rehearse', hidden);
  assert.equal(r.status, 0, r.stderr);
});

function pixelAt(file, seconds) {
  const out = execFileSync('ffmpeg', ['-v', 'error', '-ss', String(seconds), '-i', file, '-frames:v', '1',
    '-vf', 'crop=8:8:iw/2:ih/2-100,scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']);
  return [...out];
}

test('chapter times line up with the video', async () => {
  const colours = {
    ...SCRIPT,
    scenes: [
      { caption: 'Red', start: '/color/ff0000', expect: [{ url: 'ff0000' }] },
      { caption: 'Blue', start: '/color/0000ff', expect: [{ url: '0000ff' }] },
    ],
  };
  const r = await run('record', colours);
  assert.equal(r.status, 0, r.stderr);
  const [red, blue] = JSON.parse(fs.readFileSync(path.join(r.out, 'chapters.json'), 'utf8'));
  const raw = path.join(r.out, 'raw.webm');
  const before = pixelAt(raw, blue.start - 0.3);
  const after = pixelAt(raw, blue.end - 0.3);
  assert.ok(before[0] > 200 && before[2] < 60, `just before scene 2: ${before}`);
  assert.ok(after[2] > 200 && after[0] < 60, `end of scene 2: ${after}`);
  assert.ok(red.start >= 0);
});

test('a drag keeps its pace on a page that is slow to handle mouse moves', async () => {
  const heavy = {
    ...SCRIPT,
    scenes: [{
      caption: 'Wire a socket on a slow page',
      start: '/board?heavy=1',
      steps: [{ drag: { css: '#handle' }, to: { css: '#socket' } }],
      expect: [{ text: 'Wired' }],
    }],
  };
  const r = await run('record', heavy);
  assert.equal(r.status, 0, r.stderr);
  const [chapter] = JSON.parse(fs.readFileSync(path.join(r.out, 'chapters.json'), 'utf8'));
  assert.ok(chapter.end - chapter.start < 10, `scene took ${chapter.end - chapter.start}s`);
});

test('a url check does not wait for slow assets', async () => {
  const slow = structuredClone(SCRIPT);
  slow.scenes = [{ caption: 'Slow page', start: '/items?slow=1', expect: [{ url: '/items' }] }];
  const r = await run('rehearse', slow);
  assert.equal(r.status, 0, r.stderr);
});

test('--scene is for rehearsal only, and must name a scene', async () => {
  const recorded = await run('record', SCRIPT, { extra: ['--scene', '1'] });
  assert.equal(recorded.status, 2);
  assert.match(recorded.stderr, /rehearse/);
  const missing = await run('rehearse', SCRIPT, { extra: ['--scene', '3'] });
  assert.equal(missing.status, 2);
  assert.match(missing.stderr, /scene 3/);
});

test('an invalid script exits 2 before opening a browser', async () => {
  const r = await run('record', { ...SCRIPT, scenes: [] });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /no scenes/);
  assert.deepEqual(fs.readdirSync(r.out), []);
});
