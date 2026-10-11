(function () {
  'use strict';
  var bubble = document.getElementById('calibration-bubble');
  var dataX = document.getElementById('data-x');
  var dataY = document.getElementById('data-y');
  var dataZ = document.getElementById('data-z');
  var btnZero = document.getElementById('btn-zero');
  var step3Circle = document.getElementById('step-3-circle');
  var step3Label = document.getElementById('step-3-label');
  var originalButton = btnZero && btnZero.innerHTML;
  var pageId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  var sequence = 0, requested = null, pending = null, rejected = null;
  var timer = null, finishing = false, acknowledged = false, live = true, revision = -1;
  var completed = false, refGx = 0, refGy = 0, refGz = 0;
  var lastGx = 0, lastGy = 0, lastGz = 0, G = 9.80665;

  function clearTimer() { if (timer !== null) clearTimeout(timer); timer = null; }
  function fmt(v) { return (v >= 0 ? '+' : '') + v.toFixed(3) + ' g'; }
  function render(status, samples) {
    var success = status === 'COMPLETE';
    if (!success) { completed = false; refGx = refGy = refGz = 0; }
    if (btnZero) {
      btnZero.disabled = status === 'SAMPLING';
      btnZero.innerHTML = success ? '校准完成' : status === 'SAMPLING' ? '采样中… ' + (samples || 0) + '/24' :
        status === 'FAILED' || status === 'CANCELLED' ? '校准未完成，点击重试' : originalButton;
      btnZero.classList.remove('bg-green-600', 'bg-primary', 'animate-pulse-soft');
      btnZero.classList.add(success ? 'bg-green-600' : 'bg-primary');
      if (!success && status !== 'SAMPLING') btnZero.classList.add('animate-pulse-soft');
    }
    if (step3Circle) {
      step3Circle.classList.remove('bg-primary', 'text-on-primary', 'bg-surface-container-highest', 'text-on-surface-variant');
      step3Circle.classList.add(success ? 'bg-primary' : 'bg-surface-container-highest', success ? 'text-on-primary' : 'text-on-surface-variant');
    }
    if (step3Label) {
      step3Label.classList.remove('text-on-surface', 'text-on-surface-variant');
      step3Label.classList.add(success ? 'text-on-surface' : 'text-on-surface-variant');
      step3Label.textContent = success ? '校准完成' : status === 'SAMPLING' ? '保持静止，采样中' : '点击归零';
    }
  }
  function cancel() {
    if (!pending) return;
    var session = pending;
    rejected = session; pending = null; finishing = false; clearTimer();
    render('CANCELLED');
    try { window.AndroidBridge.cancelCalibration(session); } catch (e) { /* Remain unsuccessful. */ }
  }

  window.__vicoUpdate = function (state) {
    if (!live) return;
    var c = state.calibration;
    if (c && c.revision >= revision) {
      // A status belongs to exactly one attempt. A timer is never a success acknowledgement.
      var matching = !pending || c.session === pending || (acknowledged && c.status === 'IDLE');
      var obsolete = (c.session === rejected && (c.status === 'COMPLETE' || c.status === 'SAMPLING')) ||
        (c.status === 'COMPLETE' && requested && c.session !== requested);
      if (matching && !obsolete) {
        revision = c.revision;
        if (pending && c.session === pending) acknowledged = true;
        if (c.status === 'COMPLETE' && state.calibrated === true && c.samples >= 24 && c.required === 24) {
          if (!completed) { refGx = state.gx || 0; refGy = state.gy || 0; refGz = state.gz || 0; }
          completed = true; pending = null; finishing = false; clearTimer(); render('COMPLETE');
        } else if (pending && c.status === 'SAMPLING') {
          render('SAMPLING', c.samples);
          if (c.samples >= 24 && c.required === 24 && !finishing) {
            finishing = true;
            try { window.AndroidBridge.finishCalibration(pending); } catch (e) { cancel(); }
          }
        } else {
          if (pending) { rejected = pending; pending = null; finishing = false; clearTimer(); }
          render(c.status === 'COMPLETE' ? 'FAILED' : c.status);
        }
      }
    } else if (!c && state.calibrated === false && !pending) {
      render('IDLE');
    }
    lastGx = state.gx || 0; lastGy = state.gy || 0; lastGz = state.gz || 0;
    if (dataX) dataX.textContent = fmt((lastGx - refGx) / G);
    if (dataY) dataY.textContent = fmt((lastGy - refGy) / G);
    if (dataZ) dataZ.textContent = fmt((lastGz - refGz) / G);
    if (bubble) bubble.style.transform = 'translate(' + Math.max(-110, Math.min(110, (lastGx - refGx) * 30)) +
      'px, ' + Math.max(-110, Math.min(110, (lastGy - refGy) * 30)) + 'px)';
  };

  if (btnZero) btnZero.addEventListener('click', function () {
    if (!live || pending) return;
    requested = pageId + '-' + (++sequence); pending = requested; finishing = false; acknowledged = false;
    render('SAMPLING', 0);
    timer = setTimeout(cancel, 5000);
    try { window.AndroidBridge.beginCalibration(requested); } catch (e) { cancel(); }
  });
  window.addEventListener('pagehide', function () { cancel(); live = false; });
  window.addEventListener('pageshow', function () { live = true; });
  document.addEventListener('visibilitychange', function () { if (document.hidden) cancel(); live = !document.hidden; });
  var backBtn = document.querySelector('header .material-symbols-outlined');
  if (backBtn) backBtn.addEventListener('click', function () {
    cancel(); live = false;
    try { window.AndroidBridge.navigate('dashboard'); } catch (e) { live = true; }
  });
})();
