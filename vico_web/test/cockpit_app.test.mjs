import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../src/app.mjs',import.meta.url),'utf8').replace(/^import .*;$/mg,'').replace('import.meta.url',"'https://vico.invalid/src/app.mjs'");
async function boot() {
  const els=new Map(),inputs=[],windowEvents={},documentEvents={};let callback,session;
  class Element{constructor(){this.hidden=false;this.value='0';this.textContent='';this.dataset={};this.handlers={};this.attrs={};this.children=[];this.classList={toggle(){}};}addEventListener(k,f){this.handlers[k]=f;}setAttribute(k,v){this.attrs[k]=v;}append(...v){this.children.push(...v)}replaceChildren(){this.children=[]}setPointerCapture(){}hasPointerCapture(){return false}focus(){}}
  const get=id=>{if(!els.has(id))els.set(id,new Element());return els.get(id)};
  get('algorithm').value='NORMAL_SEAM_ENVELOPE_V1';
  class AudioSession{constructor(base,cb){callback=cb;session=this;this.stage='idle';this.starts=0;}setInput(v){inputs.push(v)}setVolume(){}start(){this.starts++;this.stage='running';callback({stage:'running'})}stop(){this.stage='idle';return Promise.resolve()}}
  const entry={id:'c63_w204_v6',name:'C63',kind:'V8',idleRpm:700,redlineRpm:7200,bankSha256:'c63'};
  const location={hash:'#/drive/c63_w204_v6'};
  const context=vm.createContext({document:{documentElement:{requestFullscreen:async()=>{throw Error('Denied')}},getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>[],addEventListener(k,f){documentEvents[k]=f},hidden:false},window:{addEventListener(k,f){windowEvents[k]=f}},location,navigator:{},AudioSession,loadCatalog:async()=>({vehicles:[entry],sourceCommit:'base'}),loadRecordedReferenceCatalog:async()=>({references:[]}),GpsSpeedInput:class{},performance:{now:()=>0},URL,Blob,setTimeout,clearTimeout,setInterval,clearInterval,console,isSecureContext:true});
  await vm.runInContext(`(async()=>{${source}})()`,context);
  return {get,inputs,callback,session,context,windowEvents};
}
test('fullscreen denial is contained and never restarts or stops the current run',async()=>{const b=await boot();b.get('start').handlers.click();await b.get('fullscreen').handlers.click();assert.match(b.get('message').textContent,/不允许全屏/);assert.equal(b.session.starts,1);assert.equal(b.session.stage,'running')});
test('keyboard pedal focus loss releases demand exactly once',async()=>{const b=await boot();b.get('pedal').handlers.keydown({code:'Space',preventDefault(){}});assert.equal(b.inputs.at(-1).scenario,'overspeed');assert.equal(b.get('pedal').attrs['aria-pressed'],'true');b.get('pedal').handlers.blur();assert.equal(b.inputs.at(-1).scenario,'decel');const n=b.inputs.length;b.get('pedal').handlers.keyup({code:'Space',preventDefault(){}});assert.equal(b.inputs.length,n);assert.equal(b.get('pedal').attrs['aria-pressed'],'false')});
test('secondary touch cannot steal a held accelerator and late release cannot change mode',async()=>{const b=await boot();const e={pointerId:1,isPrimary:true,preventDefault(){}};b.get('pedal').handlers.pointerdown(e);const n=b.inputs.length;b.get('pedal').handlers.pointerdown({...e,pointerId:2,isPrimary:false});b.get('pedal').handlers.pointerup({pointerId:2});assert.equal(b.inputs.length,n);await b.get('mode-manual').handlers.click();b.get('pedal').handlers.pointerup({pointerId:1});assert.equal(b.inputs.at(-1).source,'manual')});
test('stale telemetry blanks rpm gear load as well as speed; diagnostics retain real historical values',async()=>{const b=await boot();b.get('start').handlers.click();b.callback({stage:'running',stats:{inputUsable:false,speedKmh:72,rpm:3000,gear:3,load:.5,bankIdentity:{bankSha256:'c63'}}});for(const id of ['speed','rpm','gear','load'])assert.equal(b.get(id).textContent,'—');assert.equal(b.get('rpm-arc').attrs['stroke-dashoffset'],'100');assert.equal(JSON.parse(b.get('diagnostics').textContent).stats.rpm,3000)});
test('hidden manual slider cannot replace the current demo source',async()=>{const b=await boot(),n=b.inputs.length;b.get('target').value='80';b.get('target').handlers.input();assert.equal(b.inputs.length,n);await b.get('mode-manual').handlers.click();b.get('target').handlers.input();assert.equal(b.inputs.at(-1).source,'manual');assert.equal(b.inputs.at(-1).speedKmh,80)});
