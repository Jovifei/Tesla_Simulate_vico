import {AudioSession,loadCatalog} from './session.mjs';
import {GpsSpeedInput} from './core.mjs';
const $=id=>document.getElementById(id),base=new URL('../',import.meta.url);
let catalog,selected,input={source:'demo',scenario:'stop'},gpsWatch=null,gpsGeneration=0,selectionGeneration=0;
const session=new AudioSession(base,update);
const names={idle:'尚未启动',loading:'资源校验中',running:'正在播放',stopping:'正在停止',error:'已停止 / 异常'};
function update(e){
  $('play-status').textContent=names[e.stage]||e.stage;
  $('start').disabled=!selected||['loading','running','stopping'].includes(e.stage);
  $('algorithm').disabled=['loading','running','stopping'].includes(e.stage);
  if(e.detail){$('message').textContent=e.detail;$('message').classList.toggle('error',e.stage==='error');}
  if(e.stats){const s=e.stats;$('speed').textContent=s.inputUsable?String(Math.round(s.speedKmh)).padStart(3,'0'):'—';$('rpm').textContent=Math.round(s.rpm).toLocaleString('en-US');$('gear').textContent=s.gear;$('load').textContent=Math.round(s.load*100);
    $('rpm-arc').setAttribute('stroke-dashoffset',String(100-Math.min(100,s.rpm/(selected?.redlineRpm||9000)*100)));
    $('signal').textContent=s.inputUsable?'音频线程运行 · 输入有效':'输入无效或失效 · 内容静音';$('sample-rate').textContent=`${s.contextSampleRate} Hz`;$('diagnostics').textContent=JSON.stringify(s,null,2);
  }
  if(e.stage==='idle'){$('signal').textContent='声音已停止';$('rpm-arc').setAttribute('stroke-dashoffset','100');}
}
function chooseInput(next){if(next.source==='gps'&&next.valid)next.receivedAt=performance.now();input=next;session.setInput(input);$('mode-tag').textContent=next.source==='gps'?'WEB GPS · 实验估算':next.source==='manual'?'MANUAL · 虚拟速度':'DEMO · 非真实车辆数据';}
function stopGps(){gpsGeneration++;if(input.source==='gps'){input={source:'gps',valid:false};session.setInput(input);}if(gpsWatch!==null)navigator.geolocation.clearWatch(gpsWatch);gpsWatch=null;}
function scenario(key){stopGps();chooseInput({source:'demo',scenario:key});document.querySelectorAll('[data-scenario]').forEach(b=>b.classList.toggle('active',b.dataset.scenario===key));}
function resetDigits(){$('speed').textContent='000';$('rpm').textContent='0';$('gear').textContent='N';$('load').textContent='0';}
async function select(entry){const generation=++selectionGeneration;stopGps();await session.stop();if(generation!==selectionGeneration)return;selected=entry;$('vehicle-name').textContent=entry.name;document.querySelectorAll('.vehicle-card').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.key===entry.id)));resetDigits();update({stage:'idle',detail:`已选择 ${entry.name}，点击开始校验声库并播放`});}
$('start').addEventListener('click',()=>{if(selected)session.start(selected,$('algorithm').value,input);});
$('stop').addEventListener('click',()=>{stopGps();session.stop(true);});
$('volume').addEventListener('input',()=>{session.setVolume(Number($('volume').value)/100);$('volume-value').textContent=$('volume').value+'%';});
$('target').addEventListener('input',()=>{stopGps();$('target-value').textContent=$('target').value+' km/h';chooseInput({source:'manual',speedKmh:Number($('target').value)});});
document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>scenario(b.dataset.scenario)));
$('pedal').addEventListener('pointerdown',e=>{e.preventDefault();$('pedal').setPointerCapture(e.pointerId);scenario('overspeed');});
for(const event of ['pointerup','pointercancel','lostpointercapture'])$('pedal').addEventListener(event,()=>scenario('decel'));
$('pedal').addEventListener('keydown',e=>{if(e.code==='Space'||e.code==='Enter'){e.preventDefault();scenario('overspeed');}});
$('pedal').addEventListener('keyup',e=>{if(e.code==='Space'||e.code==='Enter'){e.preventDefault();scenario('decel');}});
$('demo').addEventListener('click',()=>{scenario('stop');$('gps-status').textContent='已停止定位；演示不使用传感器';});
$('gps').addEventListener('click',()=>{
  stopGps();const generation=gpsGeneration,source=new GpsSpeedInput();chooseInput({source:'gps',valid:false});
  if(!isSecureContext||!navigator.geolocation){$('gps-status').textContent='定位不可用：需要 HTTPS 与浏览器支持';return;}
  $('gps-status').textContent='等待浏览器定位授权；不保存/上传坐标';
  gpsWatch=navigator.geolocation.watchPosition(position=>{
    if(generation!==gpsGeneration)return;const packet=source.accept(position);chooseInput({...packet,source:'gps'});
    $('gps-status').textContent=packet.valid?`实验速度 ${packet.speedKmh.toFixed(1)} km/h · 非 Android REAL 等价`:'速度未知或陈旧；不使用经纬度计算替代';
  },error=>{if(generation!==gpsGeneration)return;chooseInput({source:'gps',valid:false});$('gps-status').textContent=`定位不可用（代码 ${error.code}），内容暂停`;},{enableHighAccuracy:true,maximumAge:0,timeout:5000});
});
$('export').addEventListener('click',()=>{
  const receipt={schema:'vico.web.diagnostic.v1',sourceCommit:catalog?.sourceCommit,webCommit:catalog?.webCommit,vehicle:selected?.id,stats:session.last||null,browser:navigator.userAgent,localOnly:true,deviceAcoustic:'NOT_EVALUATED',road:'NOT_RUN',human:'NOT_EVALUATED',note:'Contains no coordinates or recorded PCM. Counters are not AudioTrack underrun measurements.'};
  const url=URL.createObjectURL(new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='vico-web-diagnostic.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
const safetyStop=()=>{stopGps();session.stop(true);};
document.addEventListener('visibilitychange',()=>{if(document.hidden)safetyStop();});window.addEventListener('pagehide',safetyStop);
window.addEventListener('keydown',e=>{if(e.key==='Escape')safetyStop();});
try{
  catalog=await loadCatalog(base);$('build-id').textContent=`WEB ${(catalog.webCommit||'unknown').slice(0,8)} / CORE ${catalog.sourceCommit.slice(0,8)}`;
  $('vehicles').replaceChildren();
  for(const [i,entry] of catalog.vehicles.entries()){
    const b=document.createElement('button');b.className='vehicle-card';b.dataset.key=entry.id;b.setAttribute('aria-pressed','false');
    const kind=document.createElement('span');kind.className='kind';kind.textContent=`${entry.kind} / 0${i+1}`;
    const line=document.createElement('span');line.className='car-line';line.textContent='▁▂▃▅▃▂▁';line.setAttribute('aria-hidden','true');
    const name=document.createElement('span');name.className='title';name.textContent=entry.name;
    const meta=document.createElement('span');meta.className='meta';meta.textContent=`${entry.idleRpm} — ${entry.redlineRpm} rpm`;
    b.append(kind,line,name,meta);b.addEventListener('click',()=>select(entry));$('vehicles').append(b);
  }
  await select(catalog.vehicles[0]);
  if(catalog.testOnly){$('message').textContent='TEST FIXTURE：当前仅为自动化测试，不是实际六车型声学数据';$('build-id').textContent='TEST FIXTURE · NOT FOR AUDITION';}
}catch(e){$('vehicles').textContent='资源未构建或校验失败';update({stage:'error',detail:`${e.message}。请先运行 vico_web/tools/build.mjs，然后通过 localhost 或 HTTPS 打开。`});}
