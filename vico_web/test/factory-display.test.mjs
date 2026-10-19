import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const src=readFileSync(new URL('../src/factory-display.js',import.meta.url),'utf8');
function boot(saved=null,denied=false){
  const elements=new Map(),listeners={},storage=new Map(saved?[['vico-web-display-style-v1',saved]]:[]);
  function element(){return {innerHTML:'',textContent:'',attrs:{},value:'auto',dataset:{},style:{},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]},querySelectorAll(){return []}};}
  const get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  const context=vm.createContext({window:{},document:{documentElement:{dataset:{cluster:'touring'}},getElementById:get,addEventListener(type,fn){listeners[type]=fn}},localStorage:{getItem(k){if(denied)throw Error('storage denied');return storage.get(k)},setItem(k,v){if(denied)throw Error('storage denied');storage.set(k,v)}},console});
  vm.runInContext(src,context);
  return {api:context.window.VicoFactory,document:context.document,get,storage,listeners};
}
test('R4 presets are soundbank-independent with six distinct auto profiles',()=>{
 const b=boot(),ids=['c63_w204_v6','hellcat_v6','ferrari_458','lfa','gtr_r35','supra_jza80'];
 assert.deepEqual(ids.map(id=>b.api.resolve(id)),['mercedes','muscle','maranello','precision','technical','heritage']);
 for(const style of ['mercedes','bmw','audi','vw','honda'])assert.equal(b.api.resolve('lfa',style),style);
 assert.equal(b.api.resolve('BMW_NON_BANK'),'mercedes');
});
test('style selection persists, but invalid and denied storage never crash',()=>{
 const b=boot();assert.equal(b.api.style(),'auto');b.listeners.change({target:{id:'display-style',value:'honda'}});
 assert.equal(b.storage.get('vico-web-display-style-v1'),'honda');assert.equal(b.api.style(),'honda');
 const n=boot('data:bad');assert.equal(n.api.style(),'auto');
 const d=boot('auto',true);d.listeners.change({target:{id:'display-style',value:'audi'}});assert.equal(d.api.style(),'audi');
});
test('one SVG stage owns all four real readout IDs and no duplicate players',()=>{
 const b=boot();b.api.prepare({id:'c63_w204_v6',redlineRpm:7200});let h=b.get('r4-stage').innerHTML;
 for(const id of ['speed','rpm','gear','load','redline-rpm','input-state','speed-label','rpm-arc'])assert.equal((h.match(new RegExp(`id="${id}"`,'g'))||[]).length,1,id);
 assert.match(h,/r4-tick-major/);assert.match(h,/144|142/);assert.doesNotMatch(h,/id=".*soundbank|AudioContext/);
});
test('physical ticks and exact redline are drawn from selected sound bank',()=>{
 const b=boot();b.api.prepare({id:'c63_w204_v6',redlineRpm:7200});const old=b.get('r4-stage').innerHTML;
 assert.match(old,/r4-red/);assert.match(old,/7200/);
 b.api.prepare({id:'c63_w204_v6',redlineRpm:6200});assert.notEqual(b.get('r4-stage').innerHTML,old);
 b.api.prepare({id:'lfa',redlineRpm:9000});assert.equal(b.api.resolve('lfa'),'precision');
});
test('digital and selected presets render one coordinated view and keep source untouched',()=>{
 const b=boot();b.api.prepare({id:'gtr_r35',redlineRpm:7000});
 const s=Object.freeze({inputUsable:true,source:'WEB_GPS_ESTIMATED',speedKmh:250,rpm:5000,gear:4,load:.7});
 b.api.update(s,true);assert.equal(b.get('speed-label').textContent,'GPS 实验估算 · 虚拟');
 assert.equal(b.get('speed').textContent,'250');assert.equal(b.get('gear').textContent,'4');
 b.document.documentElement.dataset.cluster='digital';b.api.prepare({id:'gtr_r35',redlineRpm:7000});assert.match(b.get('r4-stage').innerHTML,/r4-hud-fill/);
});
test('invalid telemetry never paints stale live speed or false load',()=>{
 const b=boot();b.api.prepare({id:'ferrari_458',redlineRpm:9000});
 b.api.update({inputUsable:true,source:'DEMO',speedKmh:100,rpm:5000,gear:2,load:.8},true);
 b.api.update({inputUsable:false,source:'DEMO',speedKmh:100,rpm:5000,gear:2,load:.8},true);
 assert.equal(b.get('speed').textContent,'—');assert.equal(b.get('rpm').textContent,'—');assert.equal(b.get('gear').textContent,'—');assert.equal(b.get('load').textContent,'—');
 assert.equal(b.get('input-state').textContent,'输入失效 · 已静音');
 b.api.update(null,false);assert.equal(b.get('speed').textContent,'000');
});
test('factory display cannot own audio, network, GPS or navigation',()=>{
 assert.doesNotMatch(src,/\b(fetch|XMLHttpRequest|AudioContext|AudioWorklet|watchPosition|pushState|replaceState|setInterval)\s*\(/);
 assert.doesNotMatch(src,/location\s*\.|import\s/);
});
