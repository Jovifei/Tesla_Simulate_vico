(function(){
  'use strict';
  var original=window.__vicoUpdate,pending=null,scheduled=false,lastUnit=null;
  function reportUnit(){
    var value='unknown';try{value=localStorage.getItem('vico-unit')||'kmh';}catch(e){}
    if(value!==lastUnit&&window.AndroidBridge&&window.AndroidBridge.reportDisplayUnit){lastUnit=value;window.AndroidBridge.reportDisplayUnit(value);}
  }
  reportUnit();
  function acknowledge(){
    var p=pending;pending=null;scheduled=false;
    if(!p||!window.AndroidBridge||!window.AndroidBridge.reportDisplayFrame)return;
    var speed=document.getElementById('live-speed'),unit=document.getElementById('speed-unit');
    var value=speed?String(speed.textContent):'',label=unit?String(unit.textContent):'';
    // Two animation callbacks are a software UI acknowledgement, not an optical display-time claim.
    window.AndroidBridge.reportDisplayFrame(String(p.uiDispatchId),String(p.controlFrameId),value,label);
  }
  window.__vicoUpdate=function(s){
    try { if(original)original(s); }
    finally {
      reportUnit();
      if(s&&s.uiDispatchId&&s.controlFrameId){pending=s;if(!scheduled){scheduled=true;requestAnimationFrame(function(){requestAnimationFrame(acknowledge);});}}
    }
  };
})();
