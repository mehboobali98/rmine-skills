import { execFileSync } from 'node:child_process';
const LOCATOR_KEYS = ['role', 'label', 'text', 'placeholder', 'testId', 'css'];
const LOCATOR_STEPS = ['click', 'hover', 'fill', 'select', 'drag'];
const NEEDS_VALUE = ['fill', 'select'];
const EXPECT_KINDS = ['visible', 'hidden', 'text', 'url'];
const FLOOR_KBPS = 150;

export const REPLY_LINE = "Reply with a time and what's wrong, and I'll pick it up before QA.";

/**
 * Seconds as m:ss, or h:mm:ss from an hour, rounded down.
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
 * The Redmine comment body. A null start numbers the line instead of timing it.
 * @param {{subject: string, branch: string, sha: string, dirty: boolean,
 *   chapters: {start: number|null, caption: string, part?: number}[],
 *   omitted?: {criterion: string, reason: string}[]}} demo
 * @returns {string}
 */
export function renderComment({ subject, branch, sha, dirty, chapters, omitted = [] }) {
  const state = dirty ? `${sha} with uncommitted changes` : sha;
  const line = (c, i) => (c.start === null ? `${i + 1}. ${c.caption}` : `${formatTime(c.start)} ${c.caption}`);
  const parts = [...new Set(chapters.map((c) => c.part).filter(Boolean))];
  const blocks = parts.length
    ? parts.map((p) => [`Part ${p}`, ...chapters.filter((c) => c.part === p).map(line)].join('\n'))
    : [chapters.map(line).join('\n')];
  const notShown = omitted.map((o) => `Not shown: ${o.criterion} (${o.reason}).`).join('\n');
  return [`Demo of ${subject}, recorded on ${branch} at ${state}.`, ...blocks.filter(Boolean), notShown, REPLY_LINE].filter(Boolean)
    .join('\n\n') + '\n';
}

/**
 * The bitrate that fits the attachment limit with 10% headroom, or tooBig below 150 kbps.
 * @param {{durationSec: number, limitBytes: number}} input
 * @returns {{bitrateKbps: number} | {tooBig: true, neededKbps: number}}
 */
export function planEncode({ durationSec, limitBytes }) {
  const bitrateKbps = Math.floor((limitBytes * 8 * 0.9) / durationSec / 1000);
  return bitrateKbps < FLOOR_KBPS ? { tooBig: true, neededKbps: FLOOR_KBPS } : { bitrateKbps };
}

/**
 * Each wall-clock mark's time in the video, measured from the sync frame.
 * @param {{marks: number[], syncWallMs: number, syncVideoSec: number}} input
 * @returns {number[]} seconds from the start of the video
 */
export function syncTimes({ marks, syncWallMs, syncVideoSec }) {
  const times = marks.map((m) => Math.round((syncVideoSec + (m - syncWallMs) / 1000) * 100) / 100);
  if (times.length && times[0] < 0) {
    throw new Error('The recording started late and missed the start of scene 1. Run it again.');
  }
  return times;
}

/**
 * Seconds into the video where the warm-up switches from black to white.
 * @param {string} file
 * @returns {number}
 */
export function findSync(file) {
  const rate = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
    '-of', 'csv=p=0', file]).toString().trim().split('/').map(Number);
  const fps = rate[0] / (rate[1] || 1);
  const luma = execFileSync('ffmpeg', ['-v', 'error', '-t', '10', '-i', file, '-vf', 'crop=8:8:iw/2:ih/2,scale=1:1,format=gray',
    '-f', 'rawvideo', '-']);
  const dark = luma.findIndex((v) => v < 64);
  const light = dark < 0 ? -1 : luma.findIndex((v, i) => i > dark && v > 192);
  if (light < 0) throw new Error('No sync frame found in the recording. Run it again.');
  return Math.round((light / fps) * 100) / 100;
}

const FRAME = { pad: 40, caption: 124, radius: 14, barTop: 30, barHeight: 3, barGap: 6 };

export const PROGRESS = { track: '0xd6dce6', fill: '0x4f46e5' };

/**
 * The finished frame's size, and where the video sits inside it.
 * @param {{width: number, height: number}} viewport
 * @returns {{width: number, height: number, x: number, y: number}}
 */
export function frameSize({ width, height }) {
  return { width: width + FRAME.pad * 2, height: height + FRAME.pad + FRAME.caption, x: FRAME.pad, y: FRAME.pad };
}

/**
 * Where step n's segment of the progress bar sits in the frame.
 * @param {{width: number, height: number}} viewport
 * @param {number} total
 * @param {number} n
 * @returns {{x: number, y: number, width: number, height: number}}
 */
export function barGeometry(viewport, total, n) {
  const { x, y } = frameSize(viewport);
  const left = x + 2;
  const segment = (viewport.width - 4 - FRAME.barGap * (total - 1)) / total;
  return {
    x: Math.round(left + (segment + FRAME.barGap) * (n - 1)),
    y: y + viewport.height + FRAME.barTop,
    width: Math.round(segment),
    height: FRAME.barHeight,
  };
}

/**
 * HTML for one scene's frame: a light canvas with a transparent rounded window for the video, and the caption below.
 * @param {{n: number, total: number, time: string|null, length: string|null, caption: string, subject: string,
 *   viewport: {width: number, height: number}}} frame
 * @returns {string}
 */
export function frameHtml({ n, total, time, length, caption, subject, viewport }) {
  const escape = (text) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const size = frameSize(viewport);
  const { x, y } = size;
  const w = viewport.width;
  const h = viewport.height;
  const r = FRAME.radius;
  const hole = `M0 0H${size.width}V${size.height}H0Z M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}`
    + `V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}`
    + `A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
  const bar = barGeometry(viewport, total, n);
  const open = time ? ` M${bar.x} ${bar.y}H${bar.x + bar.width}V${bar.y + bar.height}H${bar.x}Z` : '';
  const bars = Array.from({ length: total }, (_, i) => {
    if (i < n - 1) return '<i class="done"></i>';
    return i === n - 1 ? '<i class="now"></i>' : '<i class=""></i>';
  }).join('');
  return `<!doctype html><html><head><style>
html,body{margin:0;width:${size.width}px;height:${size.height}px;background:transparent;overflow:hidden;
font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.canvas{position:absolute;inset:0;clip-path:path(evenodd,"${hole}${open}");
background:radial-gradient(120% 90% at 50% 0%,#ffffff 0%,#f1f4f9 55%,#e6ebf2 100%)}
.window{position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:${r}px;
box-shadow:0 0 0 1px rgba(15,23,42,.08),0 24px 60px -12px rgba(15,23,42,.28),0 8px 18px -8px rgba(15,23,42,.18)}
.bars{position:absolute;left:${x + 2}px;right:${x + 2}px;top:${bar.y}px;display:flex;gap:${FRAME.barGap}px}
.bars i{flex:1;height:${FRAME.barHeight}px;border-radius:2px;background:#d6dce6}.bars i.done{background:#4f46e5}
.bars i.now{background:${time ? 'transparent' : '#818cf8'}}
.cap{position:absolute;left:${x + 2}px;right:${x + 2}px;top:${y + h + 46}px;display:flex;align-items:flex-end;gap:32px}
.left{flex:1;min-width:0}
.step{font-size:13px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#4f46e5;margin-bottom:6px}
.text{font-size:30px;font-weight:650;letter-spacing:-.01em;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.right{text-align:right;color:#64748b;font-size:14px;font-weight:500;line-height:1.6;white-space:nowrap}
.time{font-variant-numeric:tabular-nums;color:#0f172a;font-weight:600}
</style></head><body><div class="canvas"></div><div class="window"></div><div class="bars">${bars}</div>
<div class="cap"><div class="left"><div class="step">Step ${n} of ${total}</div><div class="text">${escape(caption)}</div></div>
<div class="right"><div>${escape(subject)}</div>${time ? `<div class="time">${time} / ${length}</div>` : ''}</div></div>
</body></html>`;
}

/**
 * An ffmpeg FFMETADATA file with one chapter per scene, so players list the chapters.
 * @param {{start: number, end: number, caption: string}[]} chapters
 * @returns {string}
 */
export function ffmetadata(chapters) {
  const escape = (text) => text.replace(/[=;#\\\n]/g, (c) => `\\${c}`);
  const blocks = chapters.map((c) => [
    '[CHAPTER]', 'TIMEBASE=1/1000', `START=${Math.round(c.start * 1000)}`, `END=${Math.round(c.end * 1000)}`, `title=${escape(c.caption)}`,
  ].join('\n'));
  return `;FFMETADATA1\n\n${blocks.join('\n\n')}\n`;
}

/**
 * The frame for a scene's contact-sheet image: inside the closing hold, after its check passed.
 * @param {{start: number, end: number}} chapter
 * @returns {number}
 */
export function sheetTime({ start, end }) {
  return Math.max((start + end) / 2, end - 0.75);
}

function locatorError(loc) {
  if (!loc || typeof loc !== 'object') return 'needs a locator';
  const keys = Object.keys(loc).filter((k) => k !== 'name' && k !== 'exact');
  if (keys.length !== 1 || !LOCATOR_KEYS.includes(keys[0])) {
    return `locator must use exactly one of ${LOCATOR_KEYS.join(', ')}`;
  }
  if ('name' in loc && keys[0] !== 'role') return 'name only goes with role';
  if ('exact' in loc && typeof loc.exact !== 'boolean') return 'exact is true or false';
  return null;
}

function stepError(step) {
  const verbs = Object.keys(step).filter((k) => k !== 'value' && k !== 'to');
  if (verbs.length !== 1) return 'a step has exactly one action';
  const [verb] = verbs;
  if (LOCATOR_STEPS.includes(verb)) {
    const err = locatorError(step[verb]);
    if (err) return err;
    if (NEEDS_VALUE.includes(verb) && typeof step.value !== 'string') return `${verb} needs a string value`;
    if (verb === 'drag') return step.to ? locatorError(step.to) : 'drag needs a to locator';
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
 * Every problem with a scene script. Empty means valid.
 * @param {object} script
 * @returns {string[]}
 */
export function validateScript(script) {
  const errors = [];
  if (!['video', 'screenshots'].includes(script.mode)) errors.push('mode must be "video" or "screenshots"');
  const vp = script.viewport;
  if (!vp || !Number.isInteger(vp.width) || !Number.isInteger(vp.height)) errors.push('viewport needs integer width and height');
  if (script.hide !== undefined && !(Array.isArray(script.hide) && script.hide.every((h) => typeof h === 'string' && h))) {
    errors.push('hide is a list of CSS selectors');
  }
  (script.omitted || []).forEach((o, i) => {
    if (typeof o.criterion !== 'string' || !o.criterion || typeof o.reason !== 'string' || !o.reason) {
      errors.push(`omitted ${i + 1}: criterion and reason are both required`);
    }
  });
  if (!Array.isArray(script.scenes) || script.scenes.length === 0) {
    errors.push('no scenes');
    return errors;
  }
  script.scenes.forEach((scene, i) => {
    const at = `scene ${i + 1}`;
    if (typeof scene.caption !== 'string' || !scene.caption.trim()) errors.push(`${at}: caption is required`);
    const continues = i > 0 && scene.start === undefined;
    if (!continues && (typeof scene.start !== 'string' || !scene.start.startsWith('/'))) {
      errors.push(`${at}: start must be a path starting with /`);
    }
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
 * True when the page shows a password field: the generic sign of a sign-in page.
 * @param {import('playwright').Page} page
 */
export async function isPasswordVisible(page) {
  return (await page.locator('input[type=password]').filter({ visible: true }).count()) > 0;
}
