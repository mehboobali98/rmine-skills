import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { renderComment } from './lib.mjs';

const ASSEMBLE = new URL('./assemble.mjs', import.meta.url).pathname;
const IDENTITY = ['--subject', 'Items list', '--branch', 'feat/items', '--sha', 'abc1234'];

function videoDir(seconds, chapters) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'demo-assemble-'));
  execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', `testsrc2=size=640x400:rate=25:duration=${seconds}`,
    '-c:v', 'libvpx', '-b:v', '1M', path.join(dir, 'raw.webm')]);
  fs.writeFileSync(path.join(dir, 'chapters.json'), JSON.stringify(chapters));
  return dir;
}

function screenshotDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'demo-assemble-'));
  for (const n of ['01', '02']) {
    execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x400', '-frames:v', '1', path.join(dir, `scene-${n}.png`)]);
  }
  fs.writeFileSync(path.join(dir, 'chapters.json'), JSON.stringify([
    { scene: 1, caption: 'First', start: null, end: null },
    { scene: 2, caption: 'Second', start: null, end: null },
  ]));
  return dir;
}

const TWO_SCENES = [
  { scene: 1, caption: 'Open the list', start: 1.5, end: 6 },
  { scene: 2, caption: 'Edit two rows', start: 6, end: 11.5 },
];

function assemble(dir, extra) {
  return new Promise((resolve) => {
    execFile(process.execPath, [ASSEMBLE, dir, ...IDENTITY, ...extra], (err, stdout, stderr) => {
      resolve({ status: err ? err.code : 0, stdout, stderr });
    });
  });
}

const duration = (file) => Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]).toString());
const read = (dir, name) => fs.readFileSync(path.join(dir, name), 'utf8');

test('video mode trims to the scenes and shifts the chapters', async () => {
  const dir = videoDir(12, TWO_SCENES);
  const r = await assemble(dir, ['--limit-mb', '5']);
  assert.equal(r.status, 0, r.stderr);
  const mp4 = path.join(dir, 'demo.mp4');
  assert.ok(fs.statSync(mp4).size < 5 * 1024 * 1024);
  assert.ok(Math.abs(duration(mp4) - 10) < 0.2, `duration ${duration(mp4)}`);
  const chapters = JSON.parse(read(dir, 'demo-chapters.json'));
  assert.deepEqual(chapters.map((c) => [c.start, c.end]), [[0, 4.5], [4.5, 10]]);
  assert.ok(fs.existsSync(path.join(dir, 'sheet.png')));
  assert.equal(read(dir, 'comment.md'), renderComment({
    subject: 'Items list', branch: 'feat/items', sha: 'abc1234', dirty: false,
    chapters: [{ start: 0, caption: 'Open the list' }, { start: 4.5, caption: 'Edit two rows' }],
  }));
  assert.match(r.stdout, new RegExp(`^attach: ${mp4}$`, 'm'));
  assert.match(r.stdout, /^comment: .*comment\.md$/m);
});

test('running twice gives the same chapters', async () => {
  const dir = videoDir(12, TWO_SCENES);
  await assemble(dir, ['--limit-mb', '5']);
  const first = read(dir, 'comment.md');
  const r = await assemble(dir, ['--limit-mb', '5']);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(read(dir, 'comment.md'), first);
  assert.deepEqual(JSON.parse(read(dir, 'chapters.json')), TWO_SCENES);
});

test('the comment lists what the demo leaves out', async () => {
  const dir = videoDir(12, TWO_SCENES);
  fs.writeFileSync(path.join(dir, 'omitted.json'), JSON.stringify([{ criterion: 'Preview cards', reason: 'no search index' }]));
  const r = await assemble(dir, ['--limit-mb', '5']);
  assert.equal(r.status, 0, r.stderr);
  assert.match(read(dir, 'comment.md'), /\n\nNot shown: Preview cards \(no search index\)\.\n\n/);
});

test('a dirty tree is named in the comment', async () => {
  const dir = videoDir(12, TWO_SCENES);
  const r = await assemble(dir, ['--limit-mb', '5', '--dirty']);
  assert.equal(r.status, 0, r.stderr);
  assert.match(read(dir, 'comment.md'), /at abc1234 with uncommitted changes\./);
});

test('a video that cannot fit at a watchable quality exits 5 with no mp4', async () => {
  const dir = videoDir(60, [{ scene: 1, caption: 'Long', start: 0, end: 60 }]);
  const r = await assemble(dir, ['--limit-mb', '0.5']);
  assert.equal(r.status, 5);
  assert.match(r.stderr, /150 kbps/);
  assert.ok(!fs.existsSync(path.join(dir, 'demo.mp4')));
});

test('an over-limit CRF encode is re-encoded at a fitting bitrate', async () => {
  const dir = videoDir(20, [{ scene: 1, caption: 'Busy', start: 0, end: 20 }]);
  const r = await assemble(dir, ['--limit-mb', '0.6']);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /^Re-encoded at \d+ kbps to fit 0\.6 MB$/m);
  assert.ok(fs.statSync(path.join(dir, 'demo.mp4')).size <= 0.6 * 1024 * 1024);
});

test('--parts 2 splits at a scene boundary and restarts the times', async () => {
  const dir = videoDir(16, [
    { scene: 1, caption: 'One', start: 1, end: 5 },
    { scene: 2, caption: 'Two', start: 5, end: 9 },
    { scene: 3, caption: 'Three', start: 9, end: 15 },
  ]);
  const r = await assemble(dir, ['--limit-mb', '5', '--parts', '2']);
  assert.equal(r.status, 0, r.stderr);
  assert.ok(Math.abs(duration(path.join(dir, 'demo-1.mp4')) - 8) < 0.2);
  assert.ok(Math.abs(duration(path.join(dir, 'demo-2.mp4')) - 6) < 0.2);
  assert.match(read(dir, 'comment.md'), /\n\nPart 1\n0:00 One\n0:04 Two\n\nPart 2\n0:00 Three\n\n/);
  assert.equal(r.stdout.match(/^attach: /gm).length, 2);
});

test('screenshots mode attaches each image and encodes nothing', async () => {
  const dir = screenshotDir();
  const r = await assemble(dir, ['--limit-mb', '5']);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout.match(/^attach: .*scene-0[12]\.png$/gm).length, 2);
  assert.match(read(dir, 'comment.md'), /\n\n1\. First\n2\. Second\n\n/);
  assert.ok(!fs.existsSync(path.join(dir, 'demo.mp4')));
});
