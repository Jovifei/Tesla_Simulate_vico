const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assets = path.resolve(__dirname, '../../Project/android/app/src/main/assets');

function harness() {
  const timers = new Map(), calls = [], listeners = {}, elements = {};
  let nextTimer = 0;
  function element(id) {
    const classes = new Set(['bg-primary', 'animate-pulse-soft']);
    return elements[id] ||= { innerHTML: '归零 (Reset)', textContent: '', disabled: false, style: {},
      classList: { add: (...xs) => xs.forEach(x => classes.add(x)), remove: (...xs) => xs.forEach(x => classes.delete(x)), contains: x => classes.has(x) },
      addEventListener: (event, fn) => { listeners[id + ':' + event] = fn; } };
  }
  const document = { hidden: false, getElementById: element, querySelector: () => element('back'),
    addEventListener: (event, fn) => { listeners['document:' + event] = fn; } };
  const window = { addEventListener: (event, fn) => { listeners['window:' + event] = fn; },
    AndroidBridge: Object.fromEntries(['beginCalibration', 'calibrateZero', 'finishCalibration', 'cancelCalibration', 'navigate'].map(name => [name, (...args) => calls.push([name, ...args])])) };
  const context = vm.createContext({ window, document, console: { log() {} }, Math, Date,
    setTimeout: (fn, ms) => { timers.set(++nextTimer, { fn, ms }); return nextTimer; },
    clearTimeout: id => timers.delete(id) });
  const html = fs.readFileSync(path.join(assets, 'screens/calibration.html'), 'utf8');
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    const source = match[1].match(/src="([^"]+)"/);
    if (source) { if (source[1].endsWith('/calibration.js')) vm.runInContext(fs.readFileSync(path.join(assets, 'calibration.js'), 'utf8'), context); }
    else if (match[2].includes('__vicoUpdate')) vm.runInContext(match[2], context);
  }
  return { calls, elements, timers, document, click: () => listeners['btn-zero:click'](),
    event: name => listeners[name]?.(), update: state => window.__vicoUpdate(state),
    tick: ms => { for (const [id, t] of [...timers]) if (t.ms <= ms) { timers.delete(id); t.fn(); } },
    state: (status, samples = 0, revision = 1, session = calls.find(c => c[0] === 'beginCalibration')?.[1]) => ({
      calibrated: status === 'COMPLETE', gx: 1, gy: 2, gz: 3,
      calibration: { session, status, samples, required: 24, revision } }) };
}
function complete(h) { return h.elements['btn-zero'].innerHTML.includes('校准完成'); }

test('elapsed 800 ms with zero samples cannot claim success', () => {
  const h = harness(); h.click(); h.tick(800);
  assert.equal(complete(h), false); assert.equal(h.calls.filter(c => c[0] === 'finishCalibration').length, 0);
});
test('double click starts one session, 23 samples wait, 24 requests finish once and waits for native ack', () => {
  const h = harness(); h.click(); h.click();
  assert.equal(h.calls.filter(c => c[0] === 'beginCalibration').length, 1);
  h.update(h.state('SAMPLING', 23)); assert.equal(h.calls.filter(c => c[0] === 'finishCalibration').length, 0);
  h.update(h.state('SAMPLING', 24, 2)); h.update(h.state('SAMPLING', 24, 2));
  assert.equal(h.calls.filter(c => c[0] === 'finishCalibration').length, 1); assert.equal(complete(h), false);
  h.update(h.state('COMPLETE', 24, 3)); assert.equal(complete(h), true); assert.equal(h.elements['btn-zero'].disabled, false);
});
test('native failure and later false state clear every success decoration', () => {
  const h = harness(); h.click(); h.update(h.state('COMPLETE', 24, 1)); assert.equal(complete(h), true);
  h.update(h.state('IDLE', 0, 2)); assert.equal(complete(h), false);
  assert.equal(h.elements['btn-zero'].classList.contains('bg-green-600'), false);
  assert.notEqual(h.elements['step-3-label'].textContent, '校准完成');
  h.click(); h.update(h.state('FAILED', 0, 3, h.calls.filter(c => c[0] === 'beginCalibration').at(-1)[1]));
  assert.equal(complete(h), false); assert.equal(h.elements['btn-zero'].disabled, false);
});
test('timeout cancels and ignores a late success', () => {
  const h = harness(); h.click(); h.tick(5000);
  assert.equal(h.calls.filter(c => c[0] === 'cancelCalibration').length, 1);
  h.update(h.state('SAMPLING', 23, 4)); assert.equal(h.elements['btn-zero'].disabled, false);
  h.update(h.state('COMPLETE', 24, 5)); assert.equal(complete(h), false);
});
test('old session and old revision cannot complete or overwrite a newer attempt', () => {
  const h = harness(); h.click(); const old = h.calls[0][1]; h.tick(5000); h.click();
  const current = h.calls.filter(c => c[0] === 'beginCalibration').at(-1)[1];
  assert.notEqual(old, current); h.update(h.state('COMPLETE', 24, 5, old)); assert.equal(complete(h), false);
  h.update(h.state('SAMPLING', 24, 6, current)); h.update(h.state('COMPLETE', 24, 7, current)); assert.equal(complete(h), true);
  h.update(h.state('IDLE', 0, 6, current)); assert.equal(complete(h), true);
});
test('page hide, hidden visibility, and back invalidate pending work', () => {
  for (const event of ['window:pagehide', 'document:visibilitychange', 'back:click']) {
    const h = harness(); h.click(); h.document.hidden = true; h.event(event); h.tick(5000);
    h.update(h.state('COMPLETE', 24, 9)); assert.equal(complete(h), false, event);
    assert.equal(h.calls.filter(c => c[0] === 'cancelCalibration').length, 1, event);
  }
});
test('missing bridge fails visibly and does not claim success', () => {
  const h = harness(); // Force bridge call failure using the native command recorder.
  h.calls.push = () => { throw Error('bridge unavailable'); }; h.click(); h.tick(5000);
  assert.equal(complete(h), false); assert.equal(h.elements['btn-zero'].disabled, false);
});

test('queued old idle or completed state cannot cancel or finish a just-clicked attempt', () => {
  const h = harness(); h.click();
  h.update(h.state('IDLE', 0, 3, ''));
  h.update(h.state('COMPLETE', 24, 4, 'older-page'));
  assert.equal(complete(h), false); assert.equal(h.elements['btn-zero'].disabled, true);
  h.update(h.state('SAMPLING', 1, 5));
  h.update(h.state('IDLE', 0, 6, ''));
  assert.equal(complete(h), false); assert.equal(h.elements['btn-zero'].disabled, false);
});
test('native success requires calibrated true and a full accepted sample count', () => {
  for (const invalid of [{ calibrated: false }, { samples: 23 }, { required: 25 }]) {
    const h = harness(); h.click(); const state = h.state('COMPLETE', 24);
    if ('calibrated' in invalid) state.calibrated = invalid.calibrated;
    else Object.assign(state.calibration, invalid);
    h.update(state); assert.equal(complete(h), false);
  }
});
