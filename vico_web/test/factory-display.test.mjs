import test from 'node:test';
import assert from 'node:assert/strict';
import {bootDisplay,factorySource,productionHtml} from './display-fixture.mjs';
const car={id:'c63_w204_v6',redlineRpm:7200};
const sample=Object.freeze({inputUsable:true,speedKmh:144,rpm:7200,gear:8,load:1,source:'DEMO'});

test('six automatic structures and five independent presets resolve safely',()=>{const b=bootDisplay();assert.deepEqual(['c63_w204_v6','hellcat_v6','ferrari_458','lfa','gtr_r35','supra_jza80'].map(id=>b.factory.resolve(id)),['mercedes','muscle','maranello','precision','technical','heritage']);for(const p of ['mercedes','bmw','audi','vw','honda'])assert.equal(b.factory.resolve('lfa',p),p);assert.equal(b.factory.resolve('__proto__'),'mercedes');});
test('style preference saves in production namespace and denial is usable',()=>{const b=bootDisplay();b.changeStyle('honda');assert.equal(b.storage.get('vico-web-display-style-v1'),'honda');assert.equal(bootDisplay({style:'honda'}).factory.style(),'honda');assert.equal(bootDisplay({style:'bad'}).factory.style(),'auto');const d=bootDisplay({style:'honda',denied:true});assert.equal(d.factory.style(),'auto');d.changeStyle('audi');assert.equal(d.factory.style(),'audi');});
test('independent display preset retains selected sound redline',()=>{const b=bootDisplay();for(const p of ['mercedes','bmw','audi','vw','honda']){b.changeStyle(p);b.api.prepare({id:'lfa',redlineRpm:9000});assert.equal(b.document.documentElement.dataset.instrument,p);assert.equal(b.get('redline-rpm').textContent,'9000');}});
test('one generated SVG owns every required live readout exactly once',()=>{const b=bootDisplay();b.api.prepare(car);const h=b.get('r4-stage').innerHTML;for(const id of ['speed','rpm','gear','load','redline-rpm','rpm-arc','load-bar'])assert.equal((h.match(new RegExp('id="'+id+'"','g'))||[]).length,1,id);assert.equal(b.get('r4-svg').getAttribute('viewBox'),'0 0 1200 360');});
test('physical tick intervals, complete major labels and fractional redline remain exact',()=>{const b=bootDisplay();b.api.prepare(car);const d=b.get('r4-svg').querySelectorAll('[data-dial]'),rpm=d.find(n=>n.dataset.dial==='rpm'),speed=d.find(n=>n.dataset.dial==='speed');assert.equal(rpm.dataset.range,'8000');assert.equal(rpm.querySelectorAll('[data-tick]').length,81);assert.equal(rpm.querySelectorAll('[data-scale]').map(n=>n.dataset.scale).join(','),'0,1000,2000,3000,4000,5000,6000,7000,8000');assert.equal(speed.querySelectorAll('[data-scale]').map(n=>n.dataset.scale).join(','),'0,40,80,120,160,200,240,280,320');assert.equal(rpm.querySelectorAll('[data-redline]')[0].dataset.redStart,'370');});
test('over-range telemetry saturates only graphics and preserves numeric readings',()=>{const b=bootDisplay();b.api.prepare(car);const s=Object.freeze({...sample,speedKmh:400,rpm:10000});b.api.update(s,true);assert.equal(b.get('speed').textContent,'400');assert.equal(b.get('rpm').textContent,'10,000');assert.equal(b.get('speed-needle').getAttribute('transform'),'rotate(360 600 147)');assert.equal(b.get('rpm-needle').getAttribute('transform'),'rotate(395 986 170)');assert.equal(s.speedKmh,400);});
test('classic W204 uses three recessed round pods inside one cluster hood',()=>{const b=bootDisplay();b.api.prepare(car);const h=b.get('r4-stage').innerHTML;for(const name of ['gear','speed','rpm'])assert.match(h,new RegExp('data-pod="'+name+'"'));assert.equal((h.match(/data-pod="/g)||[]).length,3);assert.match(h,/data-cluster-shell="true"/);assert.equal(b.get('speed-needle').getAttribute('data-zero'),'180');assert.equal(b.get('speed-needle').dataset.max,'320');});
test('S2000 presentation draws true semicircular RPM segments while retaining the selected sound redline',()=>{const b=bootDisplay();b.changeStyle('honda');b.api.prepare(car);const h=b.get('r4-stage').innerHTML;assert.match(h,/data-rpm-geometry="semicircle"/);assert.equal((h.match(/data-rpm-step="/g)||[]).length,100);assert.doesNotMatch(h,/<rect[^>]+data-rpm-step=/);assert.match(h,/data-rpm-step="7300" class="r5-segment-stroke red"/);assert.equal(b.get('redline-rpm').textContent,'7200');});
test('Audi preset uses two complete virtual cockpit rings inside the shared hood',()=>{const b=bootDisplay();b.changeStyle('audi');const h=b.get('r4-stage').innerHTML;assert.match(h,/data-cluster-shell="true"/);assert.equal((h.match(/data-dial="/g)||[]).length,2);assert.doesNotMatch(h,/<path[^>]*class="r5-face"/);});
test('GTI upper tach arc keeps five spaced major numerals clear of its central speed',()=>{const b=bootDisplay();b.changeStyle('vw');const rpm=b.get('r4-svg').querySelectorAll('[data-dial]')[0];assert.equal(rpm.querySelectorAll('[data-scale]').map(n=>n.dataset.scale).join(','),'0,2000,4000,6000,8000');assert.equal(b.get('speed').getAttribute('font-size'),'136');});
test('invalid and nonfinite inputs never retain live values or moving needles',()=>{const b=bootDisplay();b.api.prepare(car);for(const patch of [{inputUsable:false},{rpm:NaN},{speedKmh:Infinity},{load:NaN}]){b.api.update(sample,true);b.api.update({...sample,...patch},true);for(const id of ['speed','rpm','gear','load'])assert.equal(b.get(id).textContent,'—');for(const id of ['rpm-needle','speed-needle']){assert.equal(b.get(id).getAttribute('visibility'),'hidden');assert.doesNotMatch(b.get(id).getAttribute('transform'),/NaN|Infinity/);}assert.equal(b.get('load-bar').getAttribute('width'),'0');assert.equal(b.get('input-state').textContent,'输入失效 · 已静音');}});
test('unapproved stopped GPS stays unknown through style/layout/mobile redraw',async()=>{const b=bootDisplay();b.get('mode-gps').setAttribute('aria-pressed','true');b.api.update(null,false);b.changeStyle('honda');b.choose('digital');await Promise.resolve();b.resize(390);b.flushFrames();for(const id of ['speed','rpm','gear','load'])assert.equal(b.get(id).textContent,'—');assert.match(b.get('speed-label').textContent,/GPS 实验/);});
test('non-GPS stop resets readings and clears load',()=>{const b=bootDisplay();b.api.prepare(car);b.api.update(sample,true);b.api.update(null,false);assert.equal(b.get('speed').textContent,'000');assert.equal(b.get('gear').textContent,'N');assert.equal(b.get('rpm').textContent,'0');assert.equal(b.get('load-bar').getAttribute('width'),'0');assert.equal(b.get('input-state').textContent,'等待启动');});
test('integer and invalid redlines have finite scale headroom and preserved threshold',()=>{const b=bootDisplay();for(const redlineRpm of [9000,NaN]){b.api.prepare({id:'lfa',redlineRpm});assert.equal(b.get('redline-rpm').textContent,'9000');const rpm=b.get('r4-svg').querySelectorAll('[data-dial]')[0];assert.equal(rpm.dataset.range,'10000');assert.equal(rpm.querySelectorAll('[data-redline]')[0].dataset.redStart,'370');assert.doesNotMatch(b.get('r4-stage').innerHTML,/NaN|Infinity/);}});
test('GPS source remains explicitly experimental while manual is model data',()=>{const b=bootDisplay();b.api.update({...sample,source:'WEB_GPS_ESTIMATED'},true);assert.match(b.get('speed-label').textContent,/GPS 实验/);b.api.update({...sample,source:'MANUAL'},true);assert.match(b.get('speed-label').textContent,/模型速度/);});
test('display cannot own audio, GPS, network, inputs or navigation',()=>{assert.doesNotMatch(factorySource,/\b(fetch|XMLHttpRequest|AudioContext|AudioWorklet|watchPosition|setInput|pushState|replaceState|setInterval)\s*\(/);assert.doesNotMatch(factorySource,/location\s*[.=]|^\s*import\s/m);});
test('production HTML excludes preview runtime and keeps original app script',()=>{assert.doesNotMatch(productionHtml,/preview-adapter|preview-catalog|VicoPreview|data-preview-only|预览动画|排版示例|预览不输出声音|设计预览|UI PREVIEW/);assert.match(productionHtml,/<script type="module" src="\.\/src\/app\.mjs"><\/script>/);for(const id of ['start','stop','mode-gps','target','pedal','diagnostics','export'])assert.equal((productionHtml.match(new RegExp('id="'+id+'"','g'))||[]).length,1,id);});


test('W7 refined originals retain legible figures and keep units above lower shell edge',()=>{
 const b=bootDisplay();
 const originals=[
  ['c63_w204_v6',7200,'mercedes',274],
  ['ferrari_458',9000,'maranello',217],
  ['lfa',9000,'precision',219],
  ['gtr_r35',7000,'technical',162],
  ['supra_jza80',7200,'heritage',272]
 ];
 for(const [id,redline,style,speedY] of originals){
  b.api.prepare({id,redlineRpm:redline});
  assert.equal(b.document.documentElement.dataset.instrument,style);
  assert.equal(Number(b.get('speed').getAttribute('y')),speedY,id);
  assert.ok(Number(b.get('speed').getAttribute('font-size'))>=110,id+' speed font');
  assert.ok(Number(b.get('gear').getAttribute('font-size'))>=70,id+' gear font');
  const svg=b.get('r4-stage').innerHTML;
  const unitYs=[...svg.matchAll(/<text x="[\d.]+" y="([\d.]+)"[^>]+class="r5-unit"/g)].map(m=>Number(m[1]));
  assert.ok(unitYs.length>=3,id+' numeric units');
  assert.ok(unitYs.every(y=>y<=329),id+' unit outside lower hood: '+unitYs);
  assert.equal(b.get('redline-rpm').textContent,String(redline));
  assert.match(svg,/data-cluster-shell="true"/);
 }
});


test('compact lower metadata stays safely inside hood with aligned load and redline',()=>{
 const b=bootDisplay({width:390});
 const cars=[
  ['c63_w204_v6',7200],['hellcat_v6',6200],['ferrari_458',9000],
  ['lfa',9000],['gtr_r35',7000],['supra_jza80',7200]
 ];
 for(const [id,redline] of cars){
  b.api.prepare({id,redlineRpm:redline});
  const svg=b.get('r4-svg');
  assert.equal(svg.getAttribute('viewBox'),'0 0 400 400');
  const loadGroup=svg.querySelectorAll('.r5-load')[0];
  const redGroup=svg.querySelectorAll('.r5-redline')[0];
  assert.ok(loadGroup && redGroup,id+' lower metadata present');
  const y=elements=>elements.map(node=>Number(node.getAttribute('y')));
  const loadYs=y(loadGroup.querySelectorAll('.r5-meta'));
  const redYs=y(redGroup.querySelectorAll('.r5-meta'));
  assert.equal(loadYs.length,3,id+' load name/value/percent');
  assert.equal(redYs.length,3,id+' redline name/value/unit');
  assert.ok(loadYs.every(n=>Number.isFinite(n)&&n<=381&&n>=375),id+' load labels touch hood: '+loadYs);
  assert.ok(redYs.every(n=>Number.isFinite(n)&&n<=381&&n>=375),id+' redline labels touch hood: '+redYs);
  assert.ok(Math.abs(loadYs[0]-redYs[0])<=6,id+' load/redline baseline separation');
  const barY=Number(b.get('load-bar').getAttribute('y'));
  assert.ok(barY>=355&&barY<=360,id+' compact bar must not overlap gear label: '+barY);
  assert.equal(b.get('redline-rpm').textContent,String(redline),id);
  assert.ok(svg.querySelectorAll('[data-rpm-step]').length>0,id+' complete RPM display preserved');
 }
});
