/** Optional, display-only device-axis acceleration viewer.
 *  No GPS, PCM, user analytics, vehicle acceleration inference or storage.
 */
export const MOTION_MAX_AGE_MS = 2500;
export const MOTION_FIRST_SAMPLE_LIMIT_MS = 5000;
const AXES = Object.freeze(['x', 'y', 'z']);

/** Prefer gravity-compensated data; never silently label gravity-inclusive data as such. */
export function readMotionSample(event) {
  for (const [field, includesGravity] of [['acceleration', false], ['accelerationIncludingGravity', true]]) {
    const a = event?.[field];
    if (a && AXES.every(axis => Number.isFinite(a[axis]))) {
      return { x: a.x, y: a.y, z: a.z, includesGravity };
    }
  }
  return null;
}

export function motionAxisText(value) {
  if (!Number.isFinite(value)) return '—';
  return (Math.abs(value) < 0.005 ? 0 : value).toFixed(2);
}

/** Environment arguments let Node tests drive real event ownership without a browser. */
export function createMotionMonitor({win, doc, now = () => win.performance.now()}) {
  const el = id => doc.getElementById(id);
  const startButton = el('motion-start');
  const stopButton = el('motion-stop');
  if (!startButton || !stopButton) return null;
  let epoch = 0, phase = 'idle', listening = false, intervalId = null;
  let lastValidAt = null, startedAt = null, lastPaintAt = -Infinity;

  function status(value) { el('motion-status').textContent = value; }
  function unknown() {
    for (const axis of AXES) el('motion-' + axis).textContent = '—';
    el('motion-kind').textContent = '无有效设备轴向数据 · m/s²';
  }
  function controls() {
    startButton.disabled = phase !== 'idle';
    stopButton.disabled = phase === 'idle';
  }
  function removeListener() {
    if (listening) { win.removeEventListener('devicemotion', onMotion); listening = false; }
    if (intervalId !== null) { win.clearInterval(intervalId); intervalId = null; }
  }
  function stop(reason = '已停止读取') {
    epoch++;
    removeListener();
    phase = 'idle'; startedAt = null; lastValidAt = null; lastPaintAt = -Infinity;
    unknown(); status(reason); controls();
  }
  function onMotion(event) {
    if (phase !== 'listening' || doc.hidden) return;
    const sample = readMotionSample(event), timestamp = now();
    if (!sample) {
      lastValidAt = null; unknown(); status('设备未提供有效的三轴数据');
      return;
    }
    const firstValid = lastValidAt === null;
    lastValidAt = timestamp;
    if (!firstValid && timestamp - lastPaintAt < 200) return;
    for (const axis of AXES) el('motion-' + axis).textContent = motionAxisText(sample[axis]);
    el('motion-kind').textContent = sample.includesGravity
      ? '含重力分量 · 设备坐标轴 · m/s²'
      : '已去除重力分量 · 设备坐标轴 · m/s²';
    status('正在读取（不参与声浪）');
    lastPaintAt = timestamp;
  }
  function checkFreshness() {
    if (phase !== 'listening') return;
    const t = now();
    if (lastValidAt === null) {
      if (t - startedAt > MOTION_FIRST_SAMPLE_LIMIT_MS) stop('未收到有效传感器数据 · 此设备可能不支持');
    } else if (t - lastValidAt > MOTION_MAX_AGE_MS) {
      lastValidAt = null;
      unknown(); status('传感器数据已过期 · 等待更新');
    }
  }
  async function start() {
    if (phase !== 'idle') return;
    if (!win.isSecureContext || !win.DeviceMotionEvent || typeof win.addEventListener !== 'function') {
      unknown(); status('不可用：需要 HTTPS 和支持设备运动的浏览器');
      return;
    }
    const owner = ++epoch;
    phase = 'pending'; status('正在请求设备运动权限…'); controls();
    let permission;
    try {
      // Must be invoked synchronously inside the explicit user click handler.
      permission = typeof win.DeviceMotionEvent.requestPermission === 'function'
        ? win.DeviceMotionEvent.requestPermission() : 'granted';
    } catch (_) {
      if (owner === epoch) stop('运动传感器权限请求失败');
      return;
    }
    try {
      const result = await permission;
      if (owner !== epoch || doc.hidden) return;
      if (result !== 'granted') { stop('设备运动权限未获得'); return; }
      startedAt = now(); lastValidAt = null;
      phase = 'listening'; listening = true;
      win.addEventListener('devicemotion', onMotion);
      intervalId = win.setInterval(checkFreshness, 500);
      status('等待设备运动数据…'); controls();
    } catch (_) {
      if (owner === epoch) stop('设备运动权限请求失败');
    }
  }

  startButton.addEventListener('click', start);
  stopButton.addEventListener('click', () => stop());
  // Closing settings or leaving this screen always releases the sensor listener.
  for (const id of ['settings-toggle', 'stop', 'back-garage', 'mode-demo', 'mode-manual', 'mode-gps']) {
    el(id)?.addEventListener('click', () => {
      if (phase !== 'idle') stop('切换页面或输入，已停止读取');
    });
  }
  doc.addEventListener('visibilitychange', () => {
    if (doc.hidden && phase !== 'idle') stop('页面隐藏，已停止读取');
  });
  win.addEventListener('pagehide', () => {
    if (phase !== 'idle') stop('页面关闭，已停止读取');
  });
  win.addEventListener('hashchange', () => {
    if (phase !== 'idle') stop('页面切换，已停止读取');
  });
  unknown(); status('未开启'); controls();
  return Object.freeze({ start, stop });
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  createMotionMonitor({ win: window, doc: document });
}
