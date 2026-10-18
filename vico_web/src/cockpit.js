/* Display only. No audio, control, network, geolocation or route ownership. */
(function () {
  'use strict';
  var key = 'vico-web-cluster-v1', layout = 'touring', redline = 9000;
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
      text.setAttribute('y', String(184 + 120 * Math.sin(angle)));
      text.setAttribute('text-anchor', 'middle');
      text.textContent = String(Math.round(maximum * i / steps / divisor * 10) / 10);
      group.append(text);
    }
  }
  function prepare(entry) {
    redline = Number.isFinite(entry.redlineRpm) && entry.redlineRpm > 0 ? entry.redlineRpm : 9000;
    ticks('rpm-ticks', redline, 6, 1000);
    ticks('speed-ticks', 160, 8, 1);
    update(null, false);
  }
  function update(stats, active) {
    var valid = active && stats && stats.inputUsable && Number.isFinite(stats.speedKmh) && Number.isFinite(stats.rpm) && Number.isFinite(stats.load);
    var rp = valid ? Math.max(0, Math.min(1, stats.rpm / redline)) : 0;
    var sp = valid ? Math.max(0, Math.min(1, stats.speedKmh / 160)) : 0;
    if ($('speed-arc')) $('speed-arc').setAttribute('stroke-dashoffset', String(100 * (1 - sp)));
    var angle = (135 + 270 * rp) * Math.PI / 180, needle = $('rpm-needle');
    if (needle) {
      needle.setAttribute('x1', String(180 + 99 * Math.cos(angle)));
      needle.setAttribute('y1', String(180 + 99 * Math.sin(angle)));
      needle.setAttribute('x2', String(180 + 145 * Math.cos(angle)));
      needle.setAttribute('y2', String(180 + 145 * Math.sin(angle)));
    }
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
