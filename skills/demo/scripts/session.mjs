#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
import { isPasswordVisible } from './lib.mjs';

const SIGNIN_TIMEOUT_MS = 15 * 60 * 1000;

function readSettings(dir) {
  const file = path.join(dir, 'settings.json');
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : null;
}

function sessionFile(dir) {
  return path.join(dir, 'session.json');
}

function fail(code, message) {
  process.stderr.write(`${message}\n`);
  process.exit(code);
}

async function open(page, url) {
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 15000 });
  } catch (err) {
    fail(3, `The app is not reachable at ${url}. Start it and run again. (${err.message.split('\n')[0]})`);
  }
}

async function check(dir) {
  const settings = readSettings(dir);
  if (!settings || !fs.existsSync(sessionFile(dir))) fail(4, 'No saved session. Sign in first with: session.mjs signin');
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ storageState: sessionFile(dir) });
    const page = await context.newPage();
    await open(page, settings.url);
    if (await isPasswordVisible(page)) fail(4, `The saved session no longer works: ${settings.url} shows a sign-in page. Sign in again.`);
    process.stdout.write(`Signed in at ${settings.url}\n`);
  } finally {
    await browser.close();
  }
}

async function signin(dir, url) {
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  fs.chmodSync(dir, 0o700);
  const settings = { max_attachment_mb: 5, ...readSettings(dir), url };
  fs.writeFileSync(path.join(dir, 'settings.json'), `${JSON.stringify(settings, null, 2)}\n`);

  const flag = path.join(dir, '.signed-in');
  fs.rmSync(flag, { force: true });
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: null });
  const page = await context.newPage();
  await open(page, url);
  process.stdout.write(`Waiting for sign-in. When done, create ${flag}\n`);

  let closed = false;
  page.on('close', () => { closed = true; });
  const deadline = Date.now() + SIGNIN_TIMEOUT_MS;
  while (!fs.existsSync(flag)) {
    if (closed) fail(6, 'The sign-in window was closed before sign-in was confirmed.');
    if (Date.now() > deadline) fail(6, 'Timed out waiting for sign-in.');
    await new Promise((r) => setTimeout(r, 500));
  }
  fs.rmSync(flag, { force: true });
  try {
    if (await isPasswordVisible(page)) fail(4, 'The page still shows a password field. Finish signing in, then confirm again.');
    await context.storageState({ path: sessionFile(dir) });
    fs.chmodSync(sessionFile(dir), 0o600);
    process.stdout.write(`Session saved for ${url}\n`);
  } finally {
    await browser.close();
  }
}

const [command, dir, url] = process.argv.slice(2);
if (command === 'check' && dir) await check(dir);
else if (command === 'signin' && dir && url) await signin(dir, url);
else fail(2, 'usage: session.mjs check <state-dir> | session.mjs signin <state-dir> <url>');
