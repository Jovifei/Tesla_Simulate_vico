/* Display only. No audio, control, network, geolocation or route ownership. */
(function () {
  'use strict';
  var key = 'vico-web-cluster-v1', layout = 'touring', redline = 9000, dialMax = 9000, speedMax = 160;
  var profiles = Object.freeze({
    c63_w204_v6: ['classic', 'CLASSIC / 中央速度 · 三筒', 8000, 320],
    hellcat_v6: ['muscle', 'MUSCLE / 双筒性能', 8000, 320],
    ferrari_458: ['maranello', 'SPORT / 中央转速', 10000, 320],
    lfa: ['precision', 'PRECISION / 精密单环', 10000, 320],
    gtr_r35: ['technical', 'PERFORMANCE / 偏置转速', 8000, 340],
    supra_jza80: ['heritage', 'HERITAGE / 复古三联', 8000, 280]
  });
  try { if (localStorage.getItem(key) === 'digital') layout = 'digital'; } catch (_) {}
  var $ = function (id) { return document.getElementById(id); };
  function apply() {
    document.documentElement.dataset.cluster = layout;
    document.querySelectorAll('[data-cluster-choice]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.clusterChoice === layout));
    });
  }
  function ticks(id, maximum, steps, divisor) {
    var group = $(id); if (!group || !document.createElementNS) return;
    group.replaceChildren();
    for (var i = 0; i <= steps; i++) {
      var angle = (135 + 270 * i / steps) * Math.PI / 180;
      var text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', String(180 + 120 * Math.cos(angle)));
      text.setAttribute('y', String(185 + 114 * Math.sin(angle)));
      text.setAttribute('text-anchor', 'middle');
      text.textContent = String(Math.round(maximum * i / steps / divisor * 10) / 10);
      group.append(text);
    }
  }
  function marks(id, count, majorEvery) {
    var group = $(id); if (!group || !document.createElementNS) return;
    group.replaceChildren();
    for (var i = 0; i <= count; i++) {
      var a = (135 + 270 * i / count) * Math.PI / 180;
      var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      var major = i % majorEvery === 0;
      var inner = major ? 130 : 141;
      line.setAttribute('x1', String(180 + inner * Math.cos(a)));
      line.setAttribute('y1', String(180 + inner * Math.sin(a)));
      line.setAttribute('x2', String(180 + 147 * Math.cos(a)));
      line.setAttribute('y2', String(180 + 147 * Math.sin(a)));
      line.setAttribute('class', major ? 'major-mark' : 'minor-mark');
      group.append(line);
    }
  }
  function needle(id, ratio) {
    var n = $(id); if (!n) return;
    var a = (135 + 270 * ratio) * Math.PI / 180;
    n.setAttribute('x1', '180'); n.setAttribute('y1', '180');
    n.setAttribute('x2', String(180 + 130 * Math.cos(a)));
    n.setAttribute('y2', String(180 + 130 * Math.sin(a)));
  }
  function prepare(entry) {
    redline = Number.isFinite(entry.redlineRpm) && entry.redlineRpm > 0 ? entry.redlineRpm : 9000;
    dialMax = (Math.floor(redline / 1000) + 1) * 1000;
    var profile = Object.hasOwn(profiles, entry.id) ? profiles[entry.id] : profiles.c63_w204_v6;
    if (Object.hasOwn(profiles, entry.id)) dialMax = Math.max(dialMax, profile[2]);
    speedMax = Object.hasOwn(profiles, entry.id) ? profile[3] : 160;
    document.documentElement.dataset.instrument = profile[0];
    if ($('instrument-style')) $('instrument-style').textContent = profile[1];
    ticks('rpm-ticks', dialMax, dialMax / 1000, 1000);
    ticks('speed-ticks', speedMax, speedMax / (speedMax > 160 ? 40 : 20), 1);
    marks('rpm-marks', dialMax / 100, 5); marks('speed-marks', speedMax / 10, 2);
    var red = $('rpm-redzone');
    if (red) {
      var start = 100 * redline / dialMax;
      red.setAttribute('stroke-dasharray', String(100 - start) + ' ' + String(start));
      red.setAttribute('stroke-dashoffset', String(-start));
    }
    update(null, false);
  }
  function update(stats, active) {
    var valid = active && stats && stats.inputUsable && Number.isFinite(stats.speedKmh) && Number.isFinite(stats.rpm) && Number.isFinite(stats.load);
    var rp = valid ? Math.max(0, Math.min(1, stats.rpm / dialMax)) : 0;
    var sp = valid ? Math.max(0, Math.min(1, stats.speedKmh / speedMax)) : 0;
    if ($('speed-arc')) $('speed-arc').setAttribute('stroke-dashoffset', String(100 * (1 - sp)));
    needle('rpm-needle', rp); needle('speed-needle', sp);
    if ($('rpm-arc')) $('rpm-arc').setAttribute('stroke-dashoffset', String(100 * (1 - rp)));
    if ($('load-bar')) $('load-bar').style.width = String(valid ? Math.max(0, Math.min(100, stats.load * 100)) : 0) + '%';
    if ($('input-state')) $('input-state').textContent = !active ? '等待启动' : valid ? (stats.source === 'WEB_GPS_ESTIMATED' ? 'GPS 实验估算' : '模型输入有效') : '输入失效 · 已静音';
    if ($('speed-label')) $('speed-label').textContent = stats && stats.source === 'WEB_GPS_ESTIMATED' ? 'GPS 实验估算' : '虚拟速度';
  }
  apply();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', apply, {once: true});
  document.addEventListener('click', function (event) {
    var button = event.target && event.target.closest && event.target.closest('[data-cluster-choice]');
    if (!button || button.disabled) return;
    var next = button.dataset.clusterChoice; if (next !== 'touring' && next !== 'digital') return;
    layout = next; try { localStorage.setItem(key, layout); } catch (_) {} apply();
  });
  window.VicoCockpit = Object.freeze({prepare: prepare, update: update});
})();
