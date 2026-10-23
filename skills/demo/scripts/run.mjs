#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
import {
  validateScript, syncTimes, findSync, isPasswordVisible, formatTime, frameHtml, frameSize,
} from './lib.mjs';

const TIMEOUT_MS = 5000;
const PACE = { warmUp: 500, lead: 1200, move: 1000, drag: 2000, after: 800, hold: 1800, typeDelay: 60 };
const OUTPUTS = /^(raw\.webm|chapters\.json|omitted\.json|frame-\d+\.png|scene-\d+\.png|failure\.(png|aria\.txt)|look\.(png|aria\.txt))$/;

class SceneFailure extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

function parseArgs(argv) {
  const [mode, scriptPath, stateDir, outDir, ...rest] = argv;
  const opts = {};
  for (let i = 0; i < rest.length; i += 2) opts[rest[i].replace(/^--/, '')] = Number(rest[i + 1]);
  return { mode, scriptPath, stateDir, outDir, scene: opts.scene, steps: opts.steps };
}

function locate(page, loc) {
  const exact = { exact: loc.exact === true };
  if (loc.role) return page.getByRole(loc.role, loc.name ? { name: loc.name, ...exact } : {});
  if (loc.label) return page.getByLabel(loc.label, exact);
  if (loc.text) return page.getByText(loc.text, exact);
  if (loc.placeholder) return page.getByPlaceholder(loc.placeholder, exact);
  if (loc.testId) return page.getByTestId(loc.testId);
  return page.locator(loc.css);
}

function describe(step) {
  return JSON.stringify(step);
}

async function glide(page, state, x, y, duration = PACE.move) {
  const [fromX, fromY] = state.pointer || [x, y - 120];
  const began = Date.now();
  for (;;) {
    const t = Math.min(1, (Date.now() - began) / duration);
    const ease = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
    await page.mouse.move(fromX + (x - fromX) * ease, fromY + (y - fromY) * ease);
    if (t === 1) break;
    await page.waitForTimeout(40);
  }
  state.pointer = [x, y];
}

async function centre(locator) {
  await locator.waitFor({ state: 'visible', timeout: TIMEOUT_MS });
  const box = await locator.boundingBox();
  return [box.x + box.width / 2, box.y + box.height / 2];
}

async function drag(page, source, target, { filmed, state }) {
  const [fromX, fromY] = await centre(source);
  if (!filmed) await page.mouse.move(fromX, fromY);
  await page.mouse.down();
  const [toX, toY] = await centre(target);
  if (filmed) await page.evaluate((b) => window.__demo.highlight(b), await target.boundingBox());
  if (filmed) await glide(page, state, toX, toY, PACE.drag);
  else await page.mouse.move(toX, toY, { steps: 10 });
  await page.mouse.up();
}

async function runStep(page, step, ctx) {
  const { base, filmed, state } = ctx;
  const [verb] = Object.keys(step).filter((k) => k !== 'value' && k !== 'to');
  if (verb === 'goto') return page.goto(base + step.goto, { waitUntil: 'domcontentloaded' });
  if (verb === 'wait') return page.waitForTimeout(step.wait);
  if (verb === 'press') return page.keyboard.press(step.press);

  const target = locate(page, step[verb]);
  await target.waitFor({ state: 'visible', timeout: TIMEOUT_MS });
  if (filmed) {
    await target.scrollIntoViewIfNeeded();
    const box = await target.boundingBox();
    await glide(page, state, box.x + box.width / 2, box.y + box.height / 2);
    await page.evaluate((b) => window.__demo.highlight(b), box);
  }
  if (verb === 'drag') return drag(page, target, locate(page, step.to), ctx);
  if (verb === 'click') return target.click({ timeout: TIMEOUT_MS });
  if (verb === 'hover') return target.hover({ timeout: TIMEOUT_MS });
  if (verb === 'select') return target.selectOption(step.value, { timeout: TIMEOUT_MS });
  if (!filmed) return target.fill(step.value, { timeout: TIMEOUT_MS });
  await target.click({ timeout: TIMEOUT_MS });
  await target.fill('');
  return target.pressSequentially(step.value, { delay: PACE.typeDelay });
}

async function runExpect(page, item) {
  const [kind] = Object.keys(item);
  if (kind === 'visible' || kind === 'hidden') {
    return locate(page, item[kind]).first().waitFor({ state: kind, timeout: TIMEOUT_MS });
  }
  if (kind === 'text') {
    return page.waitForFunction((t) => document.body.innerText.includes(t), item.text, { timeout: TIMEOUT_MS });
  }
  return page.waitForURL((u) => u.href.includes(item.url), { timeout: TIMEOUT_MS, waitUntil: 'commit' });
}

async function guardSignedIn(page) {
  if (await isPasswordVisible(page)) {
    throw new SceneFailure(4, 'the app is showing a sign-in page. Run session.mjs signin again; nothing was recorded.');
  }
}

async function runScene(page, scene, ctx, stopAfter) {
  const { base, filmed } = ctx;
  if (scene.start !== undefined) await page.goto(base + scene.start, { waitUntil: 'domcontentloaded' });
  await guardSignedIn(page);
  ctx.ready();
  if (filmed) await page.waitForTimeout(PACE.lead);
  const steps = stopAfter === undefined ? scene.steps || [] : (scene.steps || []).slice(0, stopAfter);
  for (const [i, step] of steps.entries()) {
    try {
      await runStep(page, step, ctx);
    } catch (err) {
      throw new SceneFailure(1, `step ${i + 1} ${describe(step)} failed: ${err.message.split('\n')[0]}`);
    }
    await page.waitForLoadState('domcontentloaded');
    await guardSignedIn(page);
    if (filmed) await page.waitForTimeout(PACE.after);
  }
  if (stopAfter !== undefined) return;
  for (const item of scene.expect) {
    try {
      await runExpect(page, item);
    } catch {
      throw new SceneFailure(1, `check ${describe(item)} did not pass`);
    }
  }
  if (filmed) await page.waitForTimeout(PACE.hold);
}

async function snapshot(page, outDir, name) {
  await page.screenshot({ path: path.join(outDir, `${name}.png`) });
  fs.writeFileSync(path.join(outDir, `${name}.aria.txt`), await page.locator('body').ariaSnapshot());
}

function clearOutputs(outDir) {
  for (const name of fs.readdirSync(outDir)) {
    if (OUTPUTS.test(name)) fs.rmSync(path.join(outDir, name), { force: true });
  }
  fs.rmSync(path.join(outDir, '.video'), { recursive: true, force: true });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!['rehearse', 'record', 'screenshots'].includes(args.mode) || !args.outDir) {
    process.stderr.write('usage: run.mjs <rehearse|record|screenshots> <script.json> <state-dir> <out-dir> [--scene N] [--steps K]\n');
    return 2;
  }
  const script = JSON.parse(fs.readFileSync(args.scriptPath, 'utf8'));
  const errors = validateScript(script);
  if (errors.length) {
    process.stderr.write(`The scene script is not valid:\n${errors.map((e) => `- ${e}`).join('\n')}\n`);
    return 2;
  }
  if ((args.scene !== undefined || args.steps !== undefined) && args.mode !== 'rehearse') {
    process.stderr.write('--scene and --steps are for rehearse only; record and screenshots run every scene.\n');
    return 2;
  }
  if (args.scene !== undefined && !script.scenes[args.scene - 1]) {
    process.stderr.write(`There is no scene ${args.scene}; the script has ${script.scenes.length}.\n`);
    return 2;
  }
  const settings = JSON.parse(fs.readFileSync(path.join(args.stateDir, 'settings.json'), 'utf8'));
  const base = settings.url.replace(/\/$/, '');
  fs.mkdirSync(args.outDir, { recursive: true });
  clearOutputs(args.outDir);

  const filmed = args.mode === 'record';
  const videoDir = path.join(args.outDir, '.video');
  const state = { pointer: null, pointerHidden: args.mode === 'screenshots', hide: script.hide || [] };
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: script.viewport,
    storageState: path.join(args.stateDir, 'session.json'),
    ...(filmed ? { recordVideo: { dir: videoDir, size: script.viewport } } : {}),
  });
  await context.exposeBinding('__demoState', () => state);
  await context.addInitScript({ path: new URL('./overlay.js', import.meta.url).pathname });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  let syncWallMs = null;
  if (filmed) {
    await page.setContent('<body style="margin:0;height:100vh;background:#000">');
    await page.waitForTimeout(PACE.warmUp);
    await page.evaluate(() => { document.body.style.background = '#fff'; });
    syncWallMs = Date.now();
    await page.waitForTimeout(PACE.warmUp);
  }

  const scenes = [...script.scenes.entries()].slice(firstScene(script, args.scene), args.scene || script.scenes.length);
  const marks = [];
  let failed = null;
  for (const [i, scene] of scenes) {
    const n = i + 1;
    const last = n === scenes[scenes.length - 1][0] + 1;
    const stopAfter = last ? args.steps : undefined;
    const ready = () => marks.push(Date.now());
    try {
      await runScene(page, scene, { base, filmed, state, ready }, stopAfter);
      marks.push(Date.now());
      if (stopAfter !== undefined) {
        process.stdout.write(`STOPPED ${n} ${scene.caption} after step ${args.steps}\n`);
      } else if (args.mode === 'screenshots') {
        await page.evaluate(() => window.__demo.hidePointer());
        await page.screenshot({ path: path.join(args.outDir, `scene-${String(n).padStart(2, '0')}.png`) });
      } else {
        process.stdout.write(`PASS ${n} ${scene.caption}\n`);
      }
    } catch (err) {
      if (!(err instanceof SceneFailure)) throw err;
      failed = err;
      process.stdout.write(`FAIL ${n} ${scene.caption}\n`);
      process.stderr.write(`scene ${n} (${scene.caption}): ${err.message}\n`);
      await snapshot(page, args.outDir, 'failure');
      process.stderr.write(`On screen: ${path.join(args.outDir, 'failure.png')} and failure.aria.txt\n`);
      break;
    }
  }
  if (!failed && args.mode === 'rehearse') {
    await snapshot(page, args.outDir, 'look');
    process.stdout.write(`look: ${path.join(args.outDir, 'look.png')}\nlook: ${path.join(args.outDir, 'look.aria.txt')}\n`);
  }

  const video = page.video();
  await context.close();

  if (filmed) {
    const raw = path.join(args.outDir, 'raw.webm');
    if (!failed) {
      fs.renameSync(await video.path(), raw);
      try {
        const times = syncTimes({ marks, syncWallMs, syncVideoSec: findSync(raw) });
        await renderFrames(browser, args.outDir, script, writeChapters(args.outDir, script, times));
      } catch (err) {
        fs.rmSync(raw, { force: true });
        failed = new SceneFailure(1, err.message);
        process.stderr.write(`${err.message}\n`);
      }
    }
    fs.rmSync(videoDir, { recursive: true, force: true });
    if (!failed) process.stdout.write(`video: ${raw}\n`);
  } else if (!failed && args.mode === 'screenshots') {
    await renderFrames(browser, args.outDir, script, writeChapters(args.outDir, script, null));
  }
  await browser.close();
  return failed ? failed.code : 0;
}

function elapsedSeconds(marks) {
  let ms = 0;
  for (let i = 0; i + 1 < marks.length - 1; i += 2) ms += marks[i + 1] - marks[i];
  return ms / 1000;
}

function sceneTag(n, total, seconds) {
  const count = `${n}/${total}`;
  return seconds === null ? count : `${count} · ${formatTime(Math.round(seconds * 100) / 100)}`;
}

function firstScene(script, scene) {
  if (!scene) return 0;
  let first = scene - 1;
  while (script.scenes[first].start === undefined) first -= 1;
  return first;
}

async function renderFrames(browser, outDir, script, chapters) {
  const { width, height } = frameSize(script.viewport);
  const last = chapters[chapters.length - 1];
  const length = last.end === null ? null : formatTime(chapters.reduce((sum, c) => sum + c.end - c.start, 0));
  const page = await browser.newPage({ viewport: { width, height } });
  for (const chapter of chapters) {
    await page.setContent(frameHtml({
      n: chapter.scene, total: chapters.length, time: chapter.time, length, caption: chapter.caption,
      subject: script.subject, viewport: script.viewport,
    }));
    await page.screenshot({ path: path.join(outDir, chapter.frame), omitBackground: true });
  }
  await page.close();
}

function writeChapters(outDir, script, times) {
  const elapsed = (i) => elapsedSeconds(times.slice(0, i * 2 + 1).map((t) => t * 1000));
  const chapters = script.scenes.map((scene, i) => ({
    scene: i + 1,
    caption: scene.caption,
    tag: sceneTag(i + 1, script.scenes.length, times ? elapsed(i) : null),
    time: times ? formatTime(Math.round(elapsed(i) * 100) / 100) : null,
    frame: `frame-${String(i + 1).padStart(2, '0')}.png`,
    criterion: scene.criterion || '',
    start: times ? times[i * 2] : null,
    end: times ? times[i * 2 + 1] : null,
    expect: scene.expect,
  }));
  fs.writeFileSync(path.join(outDir, 'chapters.json'), `${JSON.stringify(chapters, null, 2)}\n`);
  if (script.omitted?.length) fs.writeFileSync(path.join(outDir, 'omitted.json'), `${JSON.stringify(script.omitted, null, 2)}\n`);
  return chapters;
}

process.exitCode = await main();
