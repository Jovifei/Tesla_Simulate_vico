/* Appearance only: no audio/session/GPS imports, no network, no route changes. */
(function () {
  'use strict';
  var key = 'vico-web-appearance-v1';
  var selected = 'cyber';
  try { if (localStorage.getItem(key) === 'minimal') selected = 'minimal'; } catch (_) {}
  function render() {
    document.documentElement.dataset.appearance = selected;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', selected === 'minimal' ? '#f3f4f2' : '#080e18');
    document.querySelectorAll('[data-appearance-choice]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.appearanceChoice === selected));
    });
  }
  render();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render, { once: true });
  document.addEventListener('click', function (event) {
    var target = event.target;
    var button = target && typeof target.closest === 'function' ? target.closest('[data-appearance-choice]') : null;
    if (!button || button.disabled) return;
    var value = button.dataset.appearanceChoice;
    if (value !== 'cyber' && value !== 'minimal') return;
    selected = value;
    try { localStorage.setItem(key, selected); } catch (_) {}
    render();
  });
})();
