#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { planEncode, renderComment, sheetTime } from './lib.mjs';

const MB = 1024 * 1024;
const CRF = 28;
const RETRY_FACTOR = 0.85;

function parseArgs(argv) {
  const [outDir, ...rest] = argv;
  const opts = { outDir, dirty: false, parts: 1 };
  for (let i = 0; i < rest.length; i += 1) {
    const key = rest[i].replace(/^--/, '');
    if (key === 'dirty') opts.dirty = true;
    else opts[key.replace(/-(\w)/g, (_, c) => c.toUpperCase())] = rest[++i];
  }
  opts.limitBytes = Number(opts.limitMb) * MB;
  opts.parts = Number(opts.parts);
  return opts;
}

const ffmpeg = (args) => execFileSync('ffmpeg', ['-v', 'error', '-y', ...args]);

function encode(raw, from, to, out, rate) {
  const quality = rate
    ? ['-b:v', `${rate}k`, '-maxrate', `${rate}k`, '-bufsize', `${rate * 2}k`]
    : ['-crf', String(CRF)];
  ffmpeg(['-ss', String(from), '-to', String(to), '-i', raw, '-c:v', 'libx264', '-preset', 'medium', ...quality,
    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', out]);
  return fs.statSync(out).size;
}

function encodeToFit(raw, from, to, out, opts) {
  if (encode(raw, from, to, out, null) <= opts.limitBytes) return null;
  const plan = planEncode({ durationSec: to - from, limitBytes: opts.limitBytes });
  if (plan.tooBig) {
    fs.rmSync(out, { force: true });
    return `${Math.round(to - from)} s of video needs at least ${plan.neededKbps} kbps to stay readable, which does not fit ${opts.limitMb} MB.`;
  }
  for (const rate of [plan.bitrateKbps, Math.floor(plan.bitrateKbps * RETRY_FACTOR)]) {
    if (encode(raw, from, to, out, rate) <= opts.limitBytes) {
      process.stdout.write(`Re-encoded at ${rate} kbps to fit ${opts.limitMb} MB\n`);
      return null;
    }
  }
  fs.rmSync(out, { force: true });
  return `Even at ${Math.floor(plan.bitrateKbps * RETRY_FACTOR)} kbps the video is over ${opts.limitMb} MB.`;
}

function splitPoint(chapters) {
  const first = chapters[0].start;
  const middle = (first + chapters[chapters.length - 1].end) / 2;
  let best = 1;
  for (let k = 1; k < chapters.length; k += 1) {
    if (Math.abs(chapters[k].start - middle) < Math.abs(chapters[best].start - middle)) best = k;
  }
  return best;
}

function contactSheet(raw, chapters, outDir) {
  const frames = chapters.map((c, i) => {
    const file = path.join(outDir, `.sheet-${String(i + 1).padStart(2, '0')}.png`);
    ffmpeg(['-ss', String(sheetTime(c)), '-i', raw, '-frames:v', '1', '-vf', 'scale=640:-2', file]);
    return file;
  });
  const cols = Math.min(3, frames.length);
  const rows = Math.ceil(frames.length / cols);
  ffmpeg(['-i', path.join(outDir, '.sheet-%02d.png'), '-vf', `tile=${cols}x${rows}:padding=8:color=white`,
    '-frames:v', '1', path.join(outDir, 'sheet.png')]);
  frames.forEach((f) => fs.rmSync(f));
}

function assembleVideo(opts, chapters) {
  const raw = path.join(opts.outDir, 'raw.webm');
  for (const name of fs.readdirSync(opts.outDir)) {
    if (/^demo(-\d+)?\.mp4$/.test(name)) fs.rmSync(path.join(opts.outDir, name));
  }
  const cut = opts.parts === 2 ? splitPoint(chapters) : chapters.length;
  const groups = opts.parts === 2 ? [chapters.slice(0, cut), chapters.slice(cut)] : [chapters];
  const files = [];
  const shifted = [];
  for (const [i, group] of groups.entries()) {
    const from = group[0].start;
    const to = group[group.length - 1].end;
    const file = path.join(opts.outDir, opts.parts === 2 ? `demo-${i + 1}.mp4` : 'demo.mp4');
    const problem = encodeToFit(raw, from, to, file, opts);
    if (problem) {
      files.forEach((f) => fs.rmSync(f, { force: true }));
      return { problem };
    }
    files.push(file);
    const shift = (t) => Math.round((t - from) * 100) / 100;
    shifted.push(...group.map((c) => ({
      ...c, start: shift(c.start), end: shift(c.end), ...(opts.parts === 2 ? { part: i + 1 } : {}),
    })));
  }
  contactSheet(raw, chapters, opts.outDir);
  return { files, chapters: shifted };
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.outDir || !opts.subject || !opts.branch || !opts.sha || !(opts.limitBytes > 0) || ![1, 2].includes(opts.parts)) {
    process.stderr.write('usage: assemble.mjs <out-dir> --subject <s> --branch <b> --sha <sha> [--dirty] --limit-mb <n> [--parts 2]\n');
    return 2;
  }
  let chapters = JSON.parse(fs.readFileSync(path.join(opts.outDir, 'chapters.json'), 'utf8'));
  let files;

  if (chapters[0].start === null) {
    files = chapters.map((c) => path.join(opts.outDir, `scene-${String(c.scene).padStart(2, '0')}.png`));
    const big = files.filter((f) => fs.statSync(f).size > opts.limitBytes);
    if (big.length) {
      process.stderr.write(`Over ${opts.limitMb} MB: ${big.join(', ')}\n`);
      return 5;
    }
  } else {
    if (opts.parts === 2 && chapters.length < 2) {
      process.stderr.write('Splitting needs at least two scenes.\n');
      return 2;
    }
    const result = assembleVideo(opts, chapters);
    if (result.problem) {
      process.stderr.write(`${result.problem} Use screenshots instead, or --parts 2.\n`);
      return 5;
    }
    ({ files, chapters } = result);
    fs.writeFileSync(path.join(opts.outDir, 'demo-chapters.json'), `${JSON.stringify(chapters, null, 2)}\n`);
  }

  const comment = path.join(opts.outDir, 'comment.md');
  fs.writeFileSync(comment, renderComment({
    subject: opts.subject, branch: opts.branch, sha: opts.sha, dirty: opts.dirty, chapters,
  }));
  process.stdout.write(`comment: ${comment}\n${files.map((f) => `attach: ${f}`).join('\n')}\n`);
  return 0;
}

process.exitCode = main();
