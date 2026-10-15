import {AudioSession,loadCatalog} from './session.mjs';
import {GpsSpeedInput} from './core.mjs';
const $=id=>document.getElementById(id),base=new URL('../',import.meta.url);
let catalog,selected,input={source:'demo',scenario:'stop'},gpsWatch=null,gpsGeneration=0,selectionGeneration=0,view='garage',mode='demo',pedalHeld=false,pedalPointer=null,transitioning=false,stopDrain=Promise.resolve();
const session=new AudioSession(base,update);
const names={idle:'尚未启动',loading:'资源校验中',running:'正在播放',stopping:'正在停止',error:'已停止 / 异常'};
function update(e){
  if(view!=='drive')return;
  $('play-status').textContent=names[e.stage]||e.stage;
  $('start').disabled=transitioning||!selected||['loading','running','stopping'].includes(e.stage);
  $('algorithm').disabled=transitioning||['loading','running','stopping'].includes(e.stage);
  if(e.detail){$('message').textContent=e.detail;$('message').classList.toggle('error',e.stage==='error');}
  if(e.stats)$('diagnostics').textContent=JSON.stringify(e.stats,null,2);
  if(e.stage!=='running'){resetDigits();$('rpm-arc').setAttribute('stroke-dashoffset','100');}
  if(e.stats&&e.stage==='running'&&!transitioning){const s=e.stats;$('speed').textContent=s.inputUsable?String(Math.round(s.speedKmh)).padStart(3,'0'):'—';$('rpm').textContent=Math.round(s.rpm).toLocaleString('en-US');$('gear').textContent=s.gear;$('load').textContent=Math.round(s.load*100);
    $('rpm-arc').setAttribute('stroke-dashoffset',String(100-Math.min(100,s.rpm/(selected?.redlineRpm||9000)*100)));
    $('signal').textContent=s.inputUsable?'音频线程运行 · 输入有效':'输入无效或失效 · 内容静音';$('sample-rate').textContent=`${s.contextSampleRate} Hz`;$('diagnostics').textContent=JSON.stringify(s,null,2);
  }
  if(e.stage==='idle'){resetDigits();$('signal').textContent='声音已停止';$('rpm-arc').setAttribute('stroke-dashoffset','100');}
}
function chooseInput(next){if(next.source==='gps'&&next.valid)next.receivedAt=performance.now();input=next;session.setInput(input);$('mode-tag').textContent=next.source==='gps'?'WEB GPS · 实验估算':next.source==='manual'?'MANUAL · 虚拟速度':'DEMO · 非真实车辆数据';}
function stopGps(){gpsGeneration++;if(input.source==='gps'){input={source:'gps',valid:false};session.setInput(input);}if(gpsWatch!==null)navigator.geolocation.clearWatch(gpsWatch);gpsWatch=null;}
function scenario(key){stopGps();chooseInput({source:'demo',scenario:key});document.querySelectorAll('[data-scenario]').forEach(b=>b.classList.toggle('active',b.dataset.scenario===key));}
function resetDigits(){$('speed').textContent=mode==='gps'?'—':'000';$('rpm').textContent='0';$('gear').textContent='N';$('load').textContent='0';}
function showView(next){view=next;document.body?.classList.toggle('cockpit',next==='drive');$('garage').hidden=next!=='garage';$('drive').hidden=next!=='drive';}
function stopAll(){const generation=++selectionGeneration;transitioning=true;pedalHeld=false;pedalPointer=null;stopGps();resetDigits();$('rpm-arc').setAttribute('stroke-dashoffset','100');update({stage:'stopping',detail:'正在停止旧会话…'});const closing=session.stop(true);stopDrain=Promise.all([stopDrain,closing]).then(()=>{if(generation===selectionGeneration){transitioning=false;update({stage:'idle',detail:'声音已停止，请点击开始'});}});return stopDrain;}
async function select(entry){const stopped=stopAll(),generation=selectionGeneration;await stopped;if(generation!==selectionGeneration)return;selected=entry;showView('drive');$('vehicle-name').textContent=entry.name;$('redline-rpm').textContent=entry.redlineRpm.toLocaleString('en-US');document.querySelectorAll('.vehicle-card').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.key===entry.id)));update({stage:'idle',detail:`已选择 ${entry.name}，点击开始校验声库并播放`});}
function navigate(hash){if(location.hash===hash)return route();location.hash=hash;}
function route(){const match=/^#\/drive\/([a-z0-9_]+)$/.exec(location.hash);const entry=match&&catalog?.vehicles.find(v=>v.id===match[1]);if(entry)return select(entry);stopAll();showView('garage');if(location.hash&&location.hash!=='#/garage'){$('vehicles').setAttribute('aria-description','未知车型，已返回车库');$('garage-error').textContent='未知车型链接，请从下方六款车型重新选择。';}else $('garage-error').textContent='';}
async function switchMode(next){if(mode===next)return;const stopped=stopAll(),generation=selectionGeneration;mode=next;resetDigits();$('demo-controls').hidden=next!=='demo';$('manual-controls').hidden=next!=='manual';$('pedal').hidden=next!=='demo';$('gps-controls').hidden=next!=='gps';document.querySelectorAll('[id^="mode-"]').forEach(b=>b.setAttribute('aria-pressed',String(b.id==='mode-'+next)));chooseInput(next==='demo'?{source:'demo',scenario:'stop'}:next==='manual'?{source:'manual',speedKmh:Number($('target').value)}:{source:'gps',valid:false});await stopped;if(generation!==selectionGeneration)return;update({stage:'idle',detail:'输入模式已切换，请点击开始；GPS 需另行授权'});}
$('start').addEventListener('click',()=>{if(view==='drive'&&selected&&!transitioning)session.start(selected,$('algorithm').value,input);});
$('stop').addEventListener('click',stopAll);
$('back-garage').addEventListener('click',()=>{stopAll();showView('garage');navigate('#/garage');});
for(const next of ['demo','manual','gps'])$('mode-'+next).addEventListener('click',()=>switchMode(next));
$('settings-toggle').addEventListener('click',()=>{const open=$('settings').hidden;$('settings').hidden=!open;$('diagnostic-panel').hidden=!open;$('settings-toggle').setAttribute('aria-expanded',String(open));});
if(document.documentElement?.requestFullscreen){$('fullscreen').hidden=false;$('fullscreen').addEventListener('click',()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen());}
window.addEventListener('hashchange',route);
$('volume').addEventListener('input',()=>{session.setVolume(Number($('volume').value)/100);$('volume-value').textContent=$('volume').value+'%';});
$('target').addEventListener('input',()=>{stopGps();$('target-value').textContent=$('target').value+' km/h';chooseInput({source:'manual',speedKmh:Number($('target').value)});});
document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>scenario(b.dataset.scenario)));
function pressPedal(pointer){if(mode!=='demo'||view!=='drive'||pedalHeld)return;pedalHeld=true;pedalPointer=pointer;scenario('overspeed');}
function releasePedal(pointer){if(!pedalHeld||mode!=='demo'||pointer!==pedalPointer)return;pedalHeld=false;pedalPointer=null;scenario('decel');}
$('pedal').addEventListener('pointerdown',e=>{e.preventDefault();$('pedal').setPointerCapture(e.pointerId);pressPedal(e.pointerId);});
for(const event of ['pointerup','pointercancel','lostpointercapture'])$('pedal').addEventListener(event,e=>releasePedal(e.pointerId));
$('pedal').addEventListener('keydown',e=>{if(e.code==='Space'||e.code==='Enter'){e.preventDefault();pressPedal('keyboard');}});
$('pedal').addEventListener('keyup',e=>{if(e.code==='Space'||e.code==='Enter'){e.preventDefault();releasePedal('keyboard');}});
$('demo').addEventListener('click',()=>{switchMode('demo');scenario('stop');$('gps-status').textContent='已停止定位；演示不使用传感器';});
$('gps').addEventListener('click',()=>{
  if(mode!=='gps'||view!=='drive')return;stopGps();const generation=gpsGeneration,source=new GpsSpeedInput();chooseInput({source:'gps',valid:false});
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
const safetyStop=()=>stopAll();
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
    b.append(kind,line,name,meta);b.addEventListener('click',()=>navigate('#/drive/'+entry.id));$('vehicles').append(b);
  }
  showView('garage');await route();
  if(catalog.testOnly){$('message').textContent='TEST FIXTURE：当前仅为自动化测试，不是实际六车型声学数据';$('build-id').textContent='TEST FIXTURE · NOT FOR AUDITION';}
}catch(e){showView('garage');$('garage-error').textContent=`资源清单不可用：${e.message}`;$('vehicles').textContent='资源未构建或校验失败';update({stage:'error',detail:`${e.message}。请先运行 vico_web/tools/build.mjs，然后通过 localhost 或 HTTPS 打开。`});}
