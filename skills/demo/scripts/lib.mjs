// Pure helpers shared by session.mjs, run.mjs and assemble.mjs. No browser, no ffmpeg.
import path from 'node:path';

const LOCATOR_KEYS = ['role', 'label', 'text', 'placeholder', 'testId', 'css'];
const LOCATOR_STEPS = ['click', 'hover', 'fill', 'select'];
const NEEDS_VALUE = ['fill', 'select'];
const EXPECT_KINDS = ['visible', 'hidden', 'text', 'url'];
const FLOOR_KBPS = 150;

export const REPLY_LINE = "Reply with a time and what's wrong, and I'll pick it up before QA.";

/**
 * Seconds as m:ss, or h:mm:ss from an hour. Fractions are dropped, so a
 * chapter never points past the moment it names.
 * @param {number} seconds
 * @returns {string}
 */
export function formatTime(seconds) {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

/**
 * The Redmine comment. Plain lines, so it reads the same in Markdown and Textile.
 * A chapter with a null start is a screenshot and gets a number instead of a time.
 * Chapters carrying a part number are grouped under "Part N" lines.
 * @param {{subject: string, branch: string, sha: string, dirty: boolean,
 *   chapters: {start: number|null, caption: string, part?: number}[]}} demo
 * @returns {string}
 */
export function renderComment({ subject, branch, sha, dirty, chapters }) {
  const state = dirty ? `${sha} with uncommitted changes` : sha;
  const line = (c, i) => (c.start === null ? `${i + 1}. ${c.caption}` : `${formatTime(c.start)} ${c.caption}`);
  const parts = [...new Set(chapters.map((c) => c.part).filter(Boolean))];
  const blocks = parts.length
    ? parts.map((p) => [`Part ${p}`, ...chapters.filter((c) => c.part === p).map(line)].join('\n'))
    : [chapters.map(line).join('\n')];
  return [`Demo of ${subject}, recorded on ${branch} at ${state}.`, ...blocks.filter(Boolean), REPLY_LINE]
    .join('\n\n') + '\n';
}

/**
 * The bitrate that fits a video into the attachment limit, with 10% headroom
 * for the container. Below 150 kbps screen text stops being worth watching.
 * @param {{durationSec: number, limitBytes: number}} input
 * @returns {{bitrateKbps: number} | {tooBig: true, neededKbps: number}}
 */
export function planEncode({ durationSec, limitBytes }) {
  const bitrateKbps = Math.floor((limitBytes * 8 * 0.9) / durationSec / 1000);
  return bitrateKbps < FLOOR_KBPS ? { tooBig: true, neededKbps: FLOOR_KBPS } : { bitrateKbps };
}

/**
 * Where each wall-clock mark falls in the recorded video. Playwright can drop
 * frames at the start of a recording but not later, so times are counted back
 * from the end, which is when the context closed.
 * @param {{marks: number[], closeMs: number, durationSec: number}} input
 * @returns {number[]} seconds from the start of the video
 */
export function videoTimes({ marks, closeMs, durationSec }) {
  const times = marks.map((m) => Math.round((durationSec - (closeMs - m) / 1000) * 100) / 100);
  if (times.length && times[0] < 0) {
    throw new Error('The recording started late and missed the start of scene 1. Run it again.');
  }
  return times;
}

function locatorError(loc) {
  if (!loc || typeof loc !== 'object') return 'needs a locator';
  const keys = Object.keys(loc).filter((k) => k !== 'name');
  if (keys.length !== 1 || !LOCATOR_KEYS.includes(keys[0])) {
    return `locator must use exactly one of ${LOCATOR_KEYS.join(', ')}`;
  }
  if ('name' in loc && keys[0] !== 'role') return 'name only goes with role';
  return null;
}

function stepError(step) {
  const verbs = Object.keys(step).filter((k) => k !== 'value');
  if (verbs.length !== 1) return 'a step has exactly one action';
  const [verb] = verbs;
  if (LOCATOR_STEPS.includes(verb)) {
    const err = locatorError(step[verb]);
    if (err) return err;
    if (NEEDS_VALUE.includes(verb) && typeof step.value !== 'string') return `${verb} needs a string value`;
    return null;
  }
  if (verb === 'goto') return typeof step.goto === 'string' && step.goto.startsWith('/') ? null : 'goto takes a path starting with /';
  if (verb === 'press') return typeof step.press === 'string' ? null : 'press takes a key name';
  if (verb === 'wait') return Number.isInteger(step.wait) && step.wait > 0 ? null : 'wait takes milliseconds';
  return `unknown step "${verb}"`;
}

function expectError(item) {
  const kinds = Object.keys(item);
  if (kinds.length !== 1 || !EXPECT_KINDS.includes(kinds[0])) return `unknown check, use one of ${EXPECT_KINDS.join(', ')}`;
  const [kind] = kinds;
  if (kind === 'visible' || kind === 'hidden') return locatorError(item[kind]);
  return typeof item[kind] === 'string' && item[kind] ? null : `${kind} takes a string`;
}

/**
 * Every problem with a scene script, one message each. Empty means valid.
 * @param {object} script
 * @returns {string[]}
 */
export function validateScript(script) {
  const errors = [];
  if (!['video', 'screenshots'].includes(script.mode)) errors.push('mode must be "video" or "screenshots"');
  const vp = script.viewport;
  if (!vp || !Number.isInteger(vp.width) || !Number.isInteger(vp.height)) errors.push('viewport needs integer width and height');
  if (!Array.isArray(script.scenes) || script.scenes.length === 0) {
    errors.push('no scenes');
    return errors;
  }
  script.scenes.forEach((scene, i) => {
    const at = `scene ${i + 1}`;
    if (typeof scene.caption !== 'string' || !scene.caption.trim()) errors.push(`${at}: caption is required`);
    if (typeof scene.start !== 'string' || !scene.start.startsWith('/')) errors.push(`${at}: start must be a path starting with /`);
    (scene.steps || []).forEach((step, j) => {
      const err = stepError(step);
      if (err) errors.push(`${at} step ${j + 1}: ${err}`);
    });
    if (!Array.isArray(scene.expect) || scene.expect.length === 0) {
      errors.push(`${at}: expect needs at least one check, or the scene proves nothing`);
    } else {
      scene.expect.forEach((item, j) => {
        const err = expectError(item);
        if (err) errors.push(`${at} expect ${j + 1}: ${err}`);
      });
    }
  });
  return errors;
}

/**
 * The per-user directory for one product repo. Every worktree of a repo
 * shares it, because they share the git common dir.
 * @param {{env: object, home: string, gitCommonDir: string}} input
 * @returns {string}
 */
export function stateDir({ env, home, gitCommonDir }) {
  const base = env.XDG_STATE_HOME || path.join(home, '.local', 'state');
  const repo = path.basename(path.dirname(path.resolve(gitCommonDir)));
  return path.join(base, 'rmine-skills', 'demo', repo);
}
