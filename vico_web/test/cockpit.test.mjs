import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const source = fs.readFileSync(new URL('../src/cockpit.js', import.meta.url), 'utf8');
function boot(saved, denied=false) {
  const elements=new Map(), handlers={}, storage=new Map(saved ? [['vico-web-cluster-v1',saved]] : []);
  function element(){return {attrs:{},style:{},textContent:'',dataset:{},children:[],setAttribute(k,v){this.attrs[k]=v},replaceChildren(){this.children=[]},append(x){this.children.push(x)}}}
  const get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
  const buttons=['touring','digital'].map(v=>Object.assign(element(),{dataset:{clusterChoice:v},closest(){return this}}));
  const context={window:{},document:{documentElement:{dataset:{}},readyState:'complete',getElementById:get,querySelectorAll:()=>buttons,createElementNS:()=>element(),addEventListener(k,f){handlers[k]=f}},localStorage:{getItem(k){if(denied)throw Error('blocked');return storage.get(k)},setItem(k,v){if(denied)throw Error('blocked');storage.set(k,v)}}};
  vm.runInNewContext(source,context);
  return {get,context,storage,buttons,api:context.window.VicoCockpit,choose(i){handlers.click({target:buttons[i]})}};
}
test('cockpit defaults to touring and persists digital without route or engine access',()=>{const b=boot();assert.equal(b.context.document.documentElement.dataset.cluster,'touring');b.choose(1);assert.equal(b.storage.get('vico-web-cluster-v1'),'digital');assert.equal(boot('digital').context.document.documentElement.dataset.cluster,'digital');assert.equal(b.buttons[1].attrs['aria-pressed'],'true')});
test('invalid or denied preference is safe; denied storage permits in-page switch',()=>{assert.equal(boot('javascript:bad').context.document.documentElement.dataset.cluster,'touring');const b=boot(null,true);b.choose(1);assert.equal(b.context.document.documentElement.dataset.cluster,'digital')});
test('each vehicle supplies its real redline to six equal-interval ticks',()=>{const b=boot();b.api.prepare({redlineRpm:7200});const ticks=b.get('rpm-ticks').children;assert.equal(ticks.length,7);assert.equal(ticks.at(-1).textContent,'7.2');b.api.prepare({redlineRpm:9000});assert.equal(b.get('rpm-ticks').children.at(-1).textContent,'9');assert.equal(b.get('speed-ticks').children.length,9)});
test('live needles and bar use actual telemetry; speed dial saturates without changing stats',()=>{const b=boot();b.api.prepare({redlineRpm:8000});const s={inputUsable:true,rpm:4000,speedKmh:80,load:.42,source:'MANUAL'};const old=JSON.stringify(s);b.api.update(s,true);assert.equal(Number(b.get('speed-arc').attrs['stroke-dashoffset']),50);assert.equal(b.get('load-bar').style.width,'42%');assert.equal(JSON.stringify(s),old);assert.ok(Math.abs(Number(b.get('rpm-needle').attrs.x2)-180)<1e-6);assert.equal(b.get('speed-label').textContent,'虚拟速度')});
test('stopped and stale input clear secondary indicators rather than leave a live needle',()=>{const b=boot();b.api.prepare({redlineRpm:7200});b.api.update({inputUsable:true,rpm:6000,speedKmh:120,load:1},true);b.api.update({inputUsable:false,rpm:6000,speedKmh:120,load:1},true);assert.equal(b.get('speed-arc').attrs['stroke-dashoffset'],'100');assert.equal(b.get('load-bar').style.width,'0%');assert.match(b.get('input-state').textContent,/失效/);b.api.update(null,false);assert.equal(b.get('input-state').textContent,'等待启动')});
test('invalid numeric display input never paints NaN or mutates audio state',()=>{const b=boot();b.api.prepare({redlineRpm:NaN});b.api.update({inputUsable:true,rpm:NaN,speedKmh:80,load:1},true);assert.equal(b.get('speed-arc').attrs['stroke-dashoffset'],'100');assert.ok(Number.isFinite(Number(b.get('rpm-needle').attrs.x1)))});
test('GPS label remains experimental and does not pretend to be a virtual target',()=>{const b=boot();b.api.update({inputUsable:true,rpm:900,speedKmh:30,load:0,source:'WEB_GPS_ESTIMATED'},true);assert.equal(b.get('speed-label').textContent,'GPS 实验估算')});
test('display source never imports or calls audio, GPS, network or navigation',()=>{assert.doesNotMatch(source,/\b(fetch|XMLHttpRequest|AudioContext|watchPosition|pushState|replaceState|setInterval)\s*\(/);assert.doesNotMatch(source,/location\s*\.|import\s/)});
