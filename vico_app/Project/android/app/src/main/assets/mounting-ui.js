(function(){
  'use strict';
  var dirty=false,pending=false,lastRevision=0,pendingRevision=0,canConfirmNative=false,previousTrusted=false;
  function el(id){return document.getElementById(id);}
  function renderConfirm(){var b=el('mount-confirm'),a=el('mount-axis'),p=el('mount-parked');if(b)b.disabled=pending||!canConfirmNative||!a||!a.value||!p||!p.checked;}
  function wire(){
    var axis=el('mount-axis'),parked=el('mount-parked'),confirm=el('mount-confirm'),moved=el('mount-moved');
    if(axis)axis.addEventListener('change',function(){dirty=true;renderConfirm();});
    if(parked)parked.addEventListener('change',renderConfirm);
    if(confirm)confirm.addEventListener('click',function(){
      if(pending||confirm.disabled||!axis||!axis.value||!parked||!parked.checked)return;
      pending=true;pendingRevision=lastRevision;confirm.disabled=true;
      window.AndroidBridge.confirmMounting(axis.value,true);
    });
    if(moved)moved.addEventListener('click',function(){window.AndroidBridge.invalidateMounting();});
  }
  function update(s){
    var m=s.mounting;if(!m)return;
    lastRevision=Number(m.requestRevision)||0;
    if(pending&&lastRevision>pendingRevision){pending=false;if(m.result==='CONFIRMED')dirty=false;}
    var axis=el('mount-axis'),confirm=el('mount-confirm'),status=el('mount-status'),summary=el('mount-summary');
    if(axis&&!dirty&&!pending)axis.value=m.selected||'';
    canConfirmNative=m.canConfirm===true;
    if(previousTrusted&&!m.trusted&&el('mount-parked'))el('mount-parked').checked=false;
    previousTrusted=m.trusted===true;
    renderConfirm();
    if(axis)axis.disabled=m.moving===true||s.running===true||pending;
    var text=m.trusted?'已确认当前固定安装':'未确认，真实声浪暂停';
    if(m.reason==='APP_BACKGROUND')text='返回后请停车确认安装未变；无需重新校准';
    if(m.reason==='PHONE_MOVED')text='手机已移动，请重新固定并确认';
    if(m.reason==='INPUT_OR_CALIBRATION_CHANGED'||m.reason==='CALIBRATION_CHANGED')text='传感器或校准已变化，请停车后重新确认';
    if(!m.calibrated)text='请先停车并完成静止校准，再确认安装方向';
    if(m.naturalPortrait===false)text='本示意仅支持自然方向为竖屏的手机，此设备暂不支持';
    if(m.moving)text='车辆正在移动，请安全停车后再设置';
    if(m.result==='REJECTED_CHECK_PARKING_CALIBRATION_IMU'&&!pending&&!m.trusted)text+='；确认未通过，请检查停车、校准和传感器状态';
    if(status)status.textContent=text;
    if(summary)summary.textContent='安装方向 · '+(m.trusted?'已确认':'待确认');
  }
  window.VicoMounting={update:update,wire:wire};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',wire);else wire();
})();
