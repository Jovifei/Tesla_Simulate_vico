const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../Project/android/app/src/main/assets');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const fresh = { gps: 'FRESH', imu: 'FRESH', speedUsable: true, accelerationUsable: true, controlUsable: true };

function page(nativePrefs = new Map(), legacy = new Map([['vico-unit', 'mph'], ['vico-theme', 'dark']]), unavailableStorage = false) {
  const elements = {}, callbacks = [], frames = [], units = [], acknowledgements = [];
  const node = id => elements[id] || (elements[id] = {
    textContent: '', classList: { toggle() {}, add() {}, remove() {} },
    addEventListener(name, callback) { callbacks.push({ id, name, callback }); }
  });
  const c = {
    window: { AndroidBridge: {
      getDisplayUnit() { const unit = nativePrefs.get('display_unit'); return unit === 'mph' ? 'mph' : 'kmh'; },
      setDisplayUnit(unit) { if (unit === 'kmh' || unit === 'mph') nativePrefs.set('display_unit', unit); },
      reportDisplayUnit(unit) { units.push(unit); },
      reportDisplayFrame(...args) { acknowledgements.push(args); }
    } },
    document: { getElementById: node },
    localStorage: {
      getItem(key) { if (unavailableStorage) throw Error('storage denied'); return legacy.get(key) || null; },
      setItem(key, value) { if (unavailableStorage) throw Error('storage denied'); legacy.set(key, value); }
    },
    requestAnimationFrame(callback) { frames.push(callback); }, console
  };
  vm.createContext(c);
  // Before the repair this asset is absent: execute the actual old page behavior to expose the bug.
  if (fs.existsSync(path.join(root, 'display-unit.js'))) vm.runInContext(read('display-unit.js'), c);
  function dashboard() {
    vm.runInContext(read('input-quality-ui.js'), c);
    const code = read('screens/dashboard.html').match(/window\.__vicoUpdate = function\(s\)\{[\s\S]*?\n\s*\};/)[0];
    vm.runInContext(code, c);
    vm.runInContext(read('telemetry-ui.js'), c);
  }
  function settings() {
    const source = read('screens/settings.html');
    vm.runInContext(source.slice(source.indexOf('var unitVal ='), source.indexOf('// 主题:')), c);
    vm.runInContext(read('telemetry-ui.js'), c);
  }
  return { c, node, callbacks, frames, units, acknowledgements, dashboard, settings, nativePrefs, legacy };
}

test('upgrade from stored mph renders actual 144 km/h and acknowledges physical speed without changing payload or other preferences', () => {
  const native = new Map([['master_volume', .63], ['selected_vehicle', 'c63_w204_v6'], ['mount_axis', 'Y']]);
  const p = page(native); const beforeNative = [...native], beforeLegacy = [...p.legacy];
  p.dashboard();
  const payload = { speed: 144, speedKmh: '144.0', accel: '2.00', inputQuality: fresh, uiDispatchId: '9007199254740993', controlFrameId: '9007199254740994' };
  const beforePayload = JSON.stringify(payload);
  p.c.window.__vicoUpdate(payload);
  assert.equal(p.node('live-speed').textContent, '144');
  assert.equal(p.node('speed-unit').textContent, 'km/h');
  assert.equal(p.node('debug-speed').textContent, '144.0 km/h');
  assert.deepEqual(p.units, ['kmh']);
  assert.deepEqual(p.acknowledgements, []);
  p.frames.shift()(); assert.deepEqual(p.acknowledgements, []); p.frames.shift()();
  assert.deepEqual(p.acknowledgements, [['9007199254740993', '9007199254740994', '144', 'km/h']]);
  assert.equal(JSON.stringify(payload), beforePayload);
  assert.deepEqual([...native], beforeNative); assert.deepEqual([...p.legacy], beforeLegacy);
});

test('settings upgrade starts km/h and explicit mph survives navigation and recreation with divergent legacy page stores', () => {
  const native = new Map([['language', 'en'], ['output_mode', 'speaker']]);
  const s = page(native); s.settings();
  assert.equal(s.node('unit-val').textContent, 'km/h');
  s.callbacks.find(e => e.id === 'row-unit').callback();
  assert.equal(s.node('unit-val').textContent, 'mph'); assert.equal(native.get('display_unit'), 'mph');
  const d = page(native, new Map([['vico-unit', 'kmh']])); d.dashboard();
  d.c.window.__vicoUpdate({ speed: 144, speedKmh: '144.0', accel: '0.0', inputQuality: fresh });
  assert.equal(d.node('live-speed').textContent, '89'); assert.equal(d.node('speed-unit').textContent, 'mph');
  assert.equal(d.node('debug-speed').textContent, '144.0 km/h'); assert.deepEqual(d.units, ['mph']);
  const restart = page(native); restart.settings(); assert.equal(restart.node('unit-val').textContent, 'mph');
  restart.callbacks.find(e => e.id === 'row-unit').callback(); assert.equal(native.get('display_unit'), 'kmh');
  assert.equal(native.get('language'), 'en'); assert.equal(native.get('output_mode'), 'speaker');
  assert.deepEqual([...s.legacy], [['vico-unit', 'mph'], ['vico-theme', 'dark']]);
});

test('native unit choice works with unavailable WebView storage and invalid GPS never invents a numeric acknowledgement', () => {
  const p = page(new Map(), new Map(), true); p.dashboard();
  p.c.window.__vicoUpdate({ speed: 144, speedKmh: '144.0', inputQuality: { ...fresh, speedUsable: false, gps: 'STALE' }, uiDispatchId: '1', controlFrameId: '2' });
  assert.equal(p.node('live-speed').textContent, '—'); assert.equal(p.node('speed-unit').textContent, 'km/h');
  p.frames.shift()(); p.frames.shift()(); assert.deepEqual(p.acknowledgements, [['1', '2', '—', 'km/h']]);
  assert.deepEqual(p.units, ['kmh']);
});

test('unit helper is loaded before page unit setup and telemetry on every shipped screen', () => {
  for (const screen of ['dashboard', 'settings', 'library', 'calibration']) {
    const html = read(`screens/${screen}.html`), helper = html.indexOf('src="file:///android_asset/display-unit.js"');
    assert.ok(helper >= 0, `${screen} must load shared unit helper`);
    assert.ok(helper < html.indexOf('src="file:///android_asset/telemetry-ui.js"'), `${screen} telemetry must observe initialized unit policy`);
    const setup = screen === 'settings' ? html.indexOf('var unitVal =') : html.indexOf('window.__vicoUpdate =');
    if (setup >= 0) assert.ok(helper < setup, `${screen} must initialize units before rendering`);
  }
});

test('browser fallback migrates old mph without clearing other data and preserves later explicit choice', () => {
  const p = page(); delete p.c.window.AndroidBridge;
  assert.ok(p.c.window.VicoDisplayUnit, 'shared policy must be available');
  assert.equal(p.c.window.VicoDisplayUnit.get(), 'kmh');
  p.c.window.VicoDisplayUnit.set('mph'); assert.equal(p.c.window.VicoDisplayUnit.get(), 'mph');
  const restarted = page(new Map(), p.legacy); delete restarted.c.window.AndroidBridge;
  assert.equal(restarted.c.window.VicoDisplayUnit.get(), 'mph');
  assert.equal(p.legacy.get('vico-theme'), 'dark'); assert.equal(p.legacy.get('vico-unit'), 'mph');
  assert.equal(p.c.window.VicoDisplayUnit.set('invalid'), 'mph');
});

test('storage-free browser fallback remains usable and native bridge failure never revives legacy mph', () => {
  const p = page(new Map(), new Map(), true); delete p.c.window.AndroidBridge;
  assert.ok(p.c.window.VicoDisplayUnit, 'shared policy must be available');
  assert.equal(p.c.window.VicoDisplayUnit.get(), 'kmh');
  assert.equal(p.c.window.VicoDisplayUnit.set('mph'), 'mph'); assert.equal(p.c.window.VicoDisplayUnit.get(), 'mph');
  const broken = page(); broken.c.window.AndroidBridge.getDisplayUnit = () => { throw Error('bridge failure'); };
  assert.equal(broken.c.window.VicoDisplayUnit.get(), 'kmh');
});
