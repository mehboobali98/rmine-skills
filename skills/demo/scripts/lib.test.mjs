import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  formatTime, renderComment, planEncode, videoTimes, validateScript, sheetTime,
} from './lib.mjs';

const MB = 1024 * 1024;

const SCRIPT = {
  issue: 123,
  subject: 'Ticket subject',
  mode: 'video',
  viewport: { width: 1280, height: 800 },
  scenes: [
    {
      caption: 'Filter the list by status',
      criterion: 'Acceptance criterion text this scene proves',
      start: '/items',
      steps: [
        { click: { role: 'button', name: 'Filters' } },
        { fill: { label: 'Status' }, value: 'Open' },
        { press: 'Enter' },
      ],
      expect: [{ visible: { text: '3 results' } }, { url: 'status=open' }],
    },
  ],
};

const withScene = (change) => {
  const s = structuredClone(SCRIPT);
  change(s.scenes[0], s);
  return s;
};

test('formatTime', () => {
  assert.equal(formatTime(0), '0:00');
  assert.equal(formatTime(42.9), '0:42');
  assert.equal(formatTime(90), '1:30');
  assert.equal(formatTime(3725), '1:02:05');
});

test('renderComment matches the frozen shape', () => {
  assert.equal(
    renderComment({
      subject: 'Bulk edit', branch: 'feat/x', sha: 'abc1234', dirty: false,
      chapters: [{ start: 0, caption: 'Open the list' }, { start: 42, caption: 'Edit two rows' }],
    }),
    'Demo of Bulk edit, recorded on feat/x at abc1234.\n\n0:00 Open the list\n0:42 Edit two rows\n\n'
      + "Reply with a time and what's wrong, and I'll pick it up before QA.\n",
  );
});

test('renderComment marks a dirty tree', () => {
  assert.match(
    renderComment({ subject: 's', branch: 'b', sha: 'abc1234', dirty: true, chapters: [] }),
    /^Demo of s, recorded on b at abc1234 with uncommitted changes\.\n/,
  );
});

test('renderComment names what the demo leaves out', () => {
  const body = renderComment({
    subject: 's', branch: 'b', sha: 'abc1234', dirty: false,
    chapters: [{ start: 0, caption: 'One' }],
    omitted: [{ criterion: 'Preview cards', reason: 'the search index was not running' }],
  });
  assert.match(body, /\n0:00 One\n\nNot shown: Preview cards \(the search index was not running\)\.\n\nReply/);
});

test('renderComment screenshots mode numbers the scenes', () => {
  const body = renderComment({
    subject: 's', branch: 'b', sha: 'abc1234', dirty: false,
    chapters: [{ start: null, caption: 'First' }, { start: null, caption: 'Second' }],
  });
  assert.match(body, /\n\n1\. First\n2\. Second\n\n/);
});

test('renderComment splits chapters into parts', () => {
  const body = renderComment({
    subject: 's', branch: 'b', sha: 'abc1234', dirty: false,
    chapters: [
      { start: 0, caption: 'One', part: 1 }, { start: 30, caption: 'Two', part: 1 },
      { start: 0, caption: 'Three', part: 2 },
    ],
  });
  assert.match(body, /\n\nPart 1\n0:00 One\n0:30 Two\n\nPart 2\n0:00 Three\n\n/);
});

test('planEncode', () => {
  assert.deepEqual(planEncode({ durationSec: 100, limitBytes: 5 * MB }), { bitrateKbps: 377 });
  assert.ok(planEncode({ durationSec: 250, limitBytes: 5 * MB }).bitrateKbps >= 150);
});

test('planEncode refuses below the floor', () => {
  assert.deepEqual(planEncode({ durationSec: 600, limitBytes: 2 * MB }), { tooBig: true, neededKbps: 150 });
});

test('videoTimes counts back from the end', () => {
  assert.deepEqual(videoTimes({ marks: [4000, 6000], closeMs: 9000, durationSec: 7 }), [2, 4]);
  assert.throws(() => videoTimes({ marks: [1000, 4000], closeMs: 9000, durationSec: 6 }), /started late/);
});

test('sheetTime shows the end of a scene, where its check passed', () => {
  assert.equal(sheetTime({ start: 10, end: 30 }), 29.25);
  assert.equal(sheetTime({ start: 10, end: 10.5 }), 10.25);
});

test('validateScript accepts the documented sample', () => {
  assert.deepEqual(validateScript(SCRIPT), []);
});

test('validateScript accepts exact matching', () => {
  assert.deepEqual(validateScript(withScene((sc) => { sc.steps.push({ click: { role: 'option', name: '1U', exact: true } }); })), []);
});

test('validateScript accepts a drag step', () => {
  assert.deepEqual(validateScript(withScene((sc) => { sc.steps.push({ drag: { text: 'Card' }, to: { text: 'Drop zone' } }); })), []);
});

test('validateScript names each problem', () => {
  const cases = [
    [withScene((_, s) => { s.scenes = []; }), /no scenes/],
    [withScene((_, s) => { s.mode = 'gif'; }), /mode/],
    [withScene((sc) => { sc.steps[0] = { click: { role: 'button', text: 'x' } }; }), /scene 1 step 1: .*one of/],
    [withScene((sc) => { sc.steps.push({ scroll: { css: 'a' } }); }), /scene 1 step 4: unknown step/],
    [withScene((sc) => { delete sc.caption; }), /scene 1: caption/],
    [withScene((sc) => { sc.expect = []; }), /scene 1: expect/],
    [withScene((sc) => { sc.steps[1] = { fill: { label: 'Status' } }; }), /scene 1 step 2: .*value/],
    [withScene((sc) => { sc.expect.push({ glows: 'x' }); }), /scene 1 expect 3: unknown/],
    [withScene((sc) => { sc.start = 'https://elsewhere.example/'; }), /scene 1: start/],
    [withScene((sc) => { sc.steps.push({ drag: { css: '#a' } }); }), /scene 1 step 4: drag needs a to locator/],
    [withScene((sc) => { sc.steps.push({ click: { text: 'a', exact: 'yes' } }); }), /scene 1 step 4: exact is true or false/],
    [withScene((_, s) => { s.omitted = [{ criterion: 'x' }]; }), /omitted 1: criterion and reason/],
  ];
  for (const [script, pattern] of cases) {
    const errors = validateScript(script);
    assert.equal(errors.length, 1, `${pattern}: ${errors.join('; ')}`);
    assert.match(errors[0], pattern);
  }
});
