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
test('each vehicle uses integer thousands with a redline separate from dial maximum',()=>{const b=boot();b.api.prepare({redlineRpm:7200});const ticks=b.get('rpm-ticks').children;assert.equal(ticks.length,9);assert.equal(ticks.at(-1).textContent,'8');b.api.prepare({redlineRpm:9000});assert.equal(b.get('rpm-ticks').children.at(-1).textContent,'10');assert.equal(b.get('speed-ticks').children.length,9)});
test('live needles and bar use actual telemetry; speed dial saturates without changing stats',()=>{const b=boot();b.api.prepare({redlineRpm:8000});const s={inputUsable:true,rpm:4500,speedKmh:80,load:.42,source:'MANUAL'};const old=JSON.stringify(s);b.api.update(s,true);assert.equal(Number(b.get('speed-arc').attrs['stroke-dashoffset']),50);assert.equal(b.get('load-bar').style.width,'42%');assert.equal(JSON.stringify(s),old);assert.ok(Math.abs(Number(b.get('rpm-needle').attrs.x2)-180)<1e-6);assert.equal(b.get('speed-label').textContent,'虚拟速度')});
test('stopped and stale input clear secondary indicators rather than leave a live needle',()=>{const b=boot();b.api.prepare({redlineRpm:7200});b.api.update({inputUsable:true,rpm:6000,speedKmh:120,load:1},true);b.api.update({inputUsable:false,rpm:6000,speedKmh:120,load:1},true);assert.equal(b.get('speed-arc').attrs['stroke-dashoffset'],'100');assert.equal(b.get('load-bar').style.width,'0%');assert.match(b.get('input-state').textContent,/失效/);b.api.update(null,false);assert.equal(b.get('input-state').textContent,'等待启动')});
test('invalid numeric display input never paints NaN or mutates audio state',()=>{const b=boot();b.api.prepare({redlineRpm:NaN});b.api.update({inputUsable:true,rpm:NaN,speedKmh:80,load:1},true);assert.equal(b.get('speed-arc').attrs['stroke-dashoffset'],'100');assert.ok(Number.isFinite(Number(b.get('rpm-needle').attrs.x1)))});
test('GPS label remains experimental and does not pretend to be a virtual target',()=>{const b=boot();b.api.update({inputUsable:true,rpm:900,speedKmh:30,load:0,source:'WEB_GPS_ESTIMATED'},true);assert.equal(b.get('speed-label').textContent,'GPS 实验估算')});
test('display source never imports or calls audio, GPS, network or navigation',()=>{assert.doesNotMatch(source,/\b(fetch|XMLHttpRequest|AudioContext|watchPosition|pushState|replaceState|setInterval)\s*\(/);assert.doesNotMatch(source,/location\s*\.|import\s/)});

test('actual vehicle IDs select distinct instrument structures and safe unknown fallback',()=>{
 const b=boot(), profiles=[['c63_w204_v6','classic'],['hellcat_v6','muscle'],['ferrari_458','maranello'],['lfa','precision'],['gtr_r35','technical'],['supra_jza80','heritage']];
 for(const [id,profile] of profiles){b.api.prepare({id,redlineRpm:7200});assert.equal(b.context.document.documentElement.dataset.instrument,profile);assert.ok(b.get('instrument-style').textContent.length>0)}
 b.api.prepare({id:'__proto__',redlineRpm:7200});assert.equal(b.context.document.documentElement.dataset.instrument,'classic');
});
test('vehicle dials have physical ticks, exact redline sector, full live needles and reset',()=>{
 const b=boot();b.api.prepare({id:'c63_w204_v6',redlineRpm:7200});
 assert.equal(b.get('rpm-marks').children.length,81);assert.equal(b.get('speed-marks').children.length,33);
 assert.equal(b.get('rpm-redzone').attrs['stroke-dasharray'],'10 90');
 const s={inputUsable:true,rpm:4000,speedKmh:160,load:.4};b.api.update(s,true);
 assert.equal(b.get('rpm-needle').attrs.x1,'180');assert.equal(b.get('rpm-needle').attrs.y1,'180');
 assert.ok(Math.abs(Number(b.get('speed-needle').attrs.x2)-180)<1e-6);
 b.api.update({...s,inputUsable:false},true);assert.equal(b.get('speed-needle').attrs.x2,b.get('rpm-needle').attrs.x2);
 assert.equal(JSON.stringify(s),JSON.stringify({inputUsable:true,rpm:4000,speedKmh:160,load:.4}));
});
test('an integer redline has a visible sector above its exact threshold',()=>{const b=boot();b.api.prepare({id:'lfa',redlineRpm:9000});assert.equal(b.get('rpm-ticks').children.at(-1).textContent,'10');assert.equal(b.get('rpm-redzone').attrs['stroke-dashoffset'],'-90');assert.equal(b.get('rpm-redzone').attrs['stroke-dasharray'],'10 90')});
test('vehicle speed scales are display-only and use regular integer tick intervals',()=>{const b=boot();b.api.prepare({id:'gtr_r35',redlineRpm:7000});assert.equal(b.get('speed-ticks').children.map(t=>t.textContent).join(','),'0,40,80,120,160,200,240,280,320');const s={inputUsable:true,rpm:9000,speedKmh:400,load:1};const before=JSON.stringify(s);b.api.update(s,true);assert.equal(b.get('speed-arc').attrs['stroke-dashoffset'],'0');assert.equal(b.get('rpm-arc').attrs['stroke-dashoffset'],'0');assert.equal(JSON.stringify(s),before)});
