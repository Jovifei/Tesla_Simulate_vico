(function(){
  'use strict';
  // A new canonical key gives upgraded installations km/h once, then preserves explicit choices.
  // Native preferences own Android units across every file:// page; legacy vico-unit is untouched.
  var browserUnit = 'kmh', browserKey = 'vico-display-unit';
  function nativeBridge(){
    var bridge = window.AndroidBridge;
    return bridge && typeof bridge.getDisplayUnit === 'function' ? bridge : null;
  }
  function get(){
    var bridge = nativeBridge();
    if (bridge) {
      try { return bridge.getDisplayUnit() === 'mph' ? 'mph' : 'kmh'; }
      catch(e) { return 'kmh'; }
    }
    try { browserUnit = localStorage.getItem(browserKey) === 'mph' ? 'mph' : 'kmh'; } catch(e){}
    return browserUnit;
  }
  function set(unit){
    if (unit !== 'kmh' && unit !== 'mph') return get();
    var bridge = nativeBridge();
    if (bridge) {
      try { bridge.setDisplayUnit(unit); } catch(e){}
      return get();
    }
    browserUnit = unit;
    try { localStorage.setItem(browserKey, unit); } catch(e){}
    return browserUnit;
  }
  window.VicoDisplayUnit = {get:get, set:set};
})();
