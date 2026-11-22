const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const file = path.resolve(__dirname, '../../Project/android/app/src/main/assets/screens/dashboard.html');
const html = fs.readFileSync(file, 'utf8');
const match = html.match(/<script>\s*\/\/ === 接收原生传感器[\s\S]*?<\/script>/);
assert.ok(match, 'dashboard script exists');
class Element {
  constructor(){this.textContent='';this.hidden=false;this.disabled=false;this.value='';this.handlers={};this.dataset={};
    this.classList={add(){},remove(){},toggle(){},replace(){}};}
  addEventListener(name,fn){this.handlers[name]=fn;} setAttribute(name,value){this[name]=value;}
  querySelector(){return new Element();}
}
const elements=new Map(), get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const calls=[], timers=[];
const document={getElementById:get,querySelectorAll:()=>[]};
const window={AndroidBridge:{setDemoMode:on=>calls.push(['mode',on]),stopAudio:()=>calls.push(['stop']),startAudio:()=>calls.push(['start'])},
  VicoDisplayUnit:{get:()=> 'kmh'},VicoInputDisplay:{format:()=>({speed:'—',unit:'km/h',accel:'—'})}};
const ctx={window,document,console,setTimeout:fn=>{timers.push(fn);return timers.length;},clearTimeout:()=>{}};
vm.runInNewContext(match[0].replace(/^<script>/,'').replace(/<\/script>$/,''),ctx);
const update=window.__vicoUpdate;
update({running:false,demo:false,v14Input:{status:'BLOCKED'}});
assert.equal(get('start-stop-btn').disabled,true);
assert.equal(get('v14-input-status').textContent,'声音包尚未通过审核');
get('v14-mode-audition').handlers.click();assert.deepEqual(calls.at(-1),['mode',true]);
update({running:true,demo:true,v14Input:{status:'VALID',origin:'SYNTHETIC_MODEL',throttle:.4,rpm:2500,load:.6,gear:0}});
assert.equal(get('v14-gear').textContent,'0');assert.equal(get('v14-rpm').textContent,'2500');
assert.equal(get('start-stop-btn').disabled,false);
get('start-stop-btn').handlers.click();assert.deepEqual(calls.at(-1),['stop']);
timers.at(-1)();assert.equal(get('v14-input-status').textContent,'输入已失效');assert.equal(get('v14-rpm').textContent,'—');
get('v14-mode-drive').handlers.click();assert.deepEqual(calls.at(-1),['mode',false]);assert.equal(get('v14-input-status').textContent,'等待输入');
console.log('PASS dashboard mode, block, readback, stale and stop fixture');
