import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startFixture, sessionWithCookie, VALID_COOKIE } from './fixture-app.mjs';

const SESSION = new URL('./session.mjs', import.meta.url).pathname;

function stateDirFor(url, session) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'demo-state-'));
  fs.writeFileSync(path.join(dir, 'settings.json'), JSON.stringify({ url, max_attachment_mb: 5 }));
  if (session) fs.writeFileSync(path.join(dir, 'session.json'), JSON.stringify(session));
  return dir;
}

const check = (dir) => new Promise((resolve) => {
  execFile(process.execPath, [SESSION, 'check', dir], (err, stdout, stderr) => {
    resolve({ status: err ? err.code : 0, stdout, stderr });
  });
});

test('check exits 3 when the app is not running', async () => {
  const app = await startFixture();
  await app.close();
  const r = await check(stateDirFor(app.url, sessionWithCookie(VALID_COOKIE)));
  assert.equal(r.status, 3, r.stderr);
  assert.match(r.stderr, new RegExp(app.url.replace(/[.]/g, '\\.')));
});

test('check exits 4 with no saved session', async () => {
  const app = await startFixture();
  try {
    const r = await check(stateDirFor(app.url, null));
    assert.equal(r.status, 4, r.stderr);
  } finally { await app.close(); }
});

test('check exits 4 when the app shows its sign-in page', async () => {
  const app = await startFixture();
  try {
    const r = await check(stateDirFor(app.url, sessionWithCookie('expired')));
    assert.equal(r.status, 4, r.stderr);
    assert.match(r.stderr, /sign in/i);
  } finally { await app.close(); }
});

test('check exits 0 with a working session', async () => {
  const app = await startFixture();
  try {
    const r = await check(stateDirFor(app.url, sessionWithCookie(VALID_COOKIE)));
    assert.equal(r.status, 0, r.stderr);
  } finally { await app.close(); }
});

test('check exits 4 with no settings', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'demo-state-'));
  assert.equal((await check(dir)).status, 4);
});
