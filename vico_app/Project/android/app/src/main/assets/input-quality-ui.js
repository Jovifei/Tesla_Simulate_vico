(function(){
  'use strict';
  var gpsLabels={FRESH:'速度有效',UNVERIFIED:'精度未报告',STALE:'速度陈旧',LOW_QUALITY:'速度精度不足',UNAVAILABLE:'等待有效定位',SYNTHETIC:'演示数据'};
  window.VicoInputDisplay={format:function(s,unit){
    var q=s.inputQuality||{}, speed=Number(s.speedKmh), usable=q.speedUsable===true&&isFinite(speed)&&speed>=0;
    var standard=isFinite(speed)&&speed>=0?speed.toFixed(1)+' km/h':'—';
    var acceleration=Number(s.accel), accelUsable=q.accelerationUsable===true&&isFinite(acceleration);
    var warnings=[];
    if(!usable) warnings.push((gpsLabels[q.gps]||gpsLabels.UNAVAILABLE)+'；当前车速未知，真实声浪暂停');
    else if(q.gps==='UNVERIFIED') warnings.push('设备未报告速度精度，当前读数未验证');
    if(q.imu==='UNCONFIRMED_FRAME') warnings.push('安装方向未确认，车辆前向加速度未知，真实声浪暂停');
    else if(!accelUsable&&q.gps!=='SYNTHETIC') warnings.push('加速度不可用，真实声浪暂停');
    return {speed:usable?String(Math.round(unit==='mph'?speed*0.621371:speed)):'—',
      unit:unit==='mph'?'mph':'km/h',standardSpeed:standard,
      accel:accelUsable?acceleration.toFixed(2):'—',
      gpsLabel:gpsLabels[q.gps]||gpsLabels.UNAVAILABLE,good:usable&&q.gps==='FRESH',
      warning:warnings.join('；'),quality:(q.gps||'UNAVAILABLE')+' / '+(q.imu||'UNAVAILABLE'),
      age:q.gpsAgeMs==null?'—':Math.round(q.gpsAgeMs)+' ms'};
  }};
})();
