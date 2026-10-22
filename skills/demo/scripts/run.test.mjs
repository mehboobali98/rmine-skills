import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startFixture, sessionWithCookie, VALID_COOKIE } from './fixture-app.mjs';

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

test('screenshots writes one image per scene', async () => {
  const r = await run('screenshots', { ...SCRIPT, mode: 'screenshots' });
  assert.equal(r.status, 0, r.stderr);
  assert.ok(exists(r.out, 'scene-01.png'));
  assert.ok(exists(r.out, 'scene-02.png'));
  const chapters = JSON.parse(fs.readFileSync(path.join(r.out, 'chapters.json'), 'utf8'));
  assert.deepEqual(chapters.map((c) => c.start), [null, null]);
});

test('an invalid script exits 2 before opening a browser', async () => {
  const r = await run('record', { ...SCRIPT, scenes: [] });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /no scenes/);
  assert.deepEqual(fs.readdirSync(r.out), []);
});
