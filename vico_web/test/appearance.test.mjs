import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const code=fs.readFileSync(new URL('../src/appearance.js',import.meta.url),'utf8');
function boot({storage=new Map(),denied=false,loading=false}={}) {
  const callbacks={},colors={},buttons=['cyber','minimal'].map(value=>({dataset:{appearanceChoice:value},disabled:false,attrs:{},setAttribute(k,v){this.attrs[k]=v;},closest(){return this;}}));
  const root={dataset:{}}, hash='#/drive/c63_w204_v6';
  const session={runId:24,vehicle:'c63_w204_v6',state:'running',volume:.2};
  const ctx={document:{documentElement:root,readyState:loading?'loading':'complete',querySelector:()=>({setAttribute(k,v){colors[k]=v}}),querySelectorAll:()=>buttons,addEventListener(k,f){callbacks[k]=f}},localStorage:{getItem(k){if(denied)throw Error('denied');return storage.get(k)??null;},setItem(k,v){if(denied)throw Error('denied');storage.set(k,v)}},location:{hash},session};
  vm.runInNewContext(code,ctx);
  return {ctx,storage,buttons,colors,root,callbacks,choose(value){callbacks.click({target:buttons.find(b=>b.dataset.appearanceChoice===value)})}};
}
test('default cyber appearance and pressed states',()=>{const b=boot();assert.equal(b.root.dataset.appearance,'cyber');assert.equal(b.buttons[0].attrs['aria-pressed'],'true');assert.equal(b.buttons[1].attrs['aria-pressed'],'false');});
test('minimal persists and survives a new page',()=>{const b=boot();b.choose('minimal');assert.equal(b.root.dataset.appearance,'minimal');assert.equal(b.colors.content,'#f3f4f2');assert.equal(boot({storage:b.storage}).root.dataset.appearance,'minimal');});
test('switch changes no route, playback identity, volume or unrelated preference',()=>{const storage=new Map([['selected_vehicle','c63_w204_v6'],['vico-unit','mph']]);const b=boot({storage}),s=JSON.stringify(b.ctx.session);b.choose('minimal');b.choose('cyber');assert.equal(b.ctx.location.hash,'#/drive/c63_w204_v6');assert.equal(JSON.stringify(b.ctx.session),s);assert.equal(storage.get('vico-unit'),'mph');assert.equal(storage.get('selected_vehicle'),'c63_w204_v6');});
test('denied storage uses safe default and allows in-page switch',()=>{const b=boot({denied:true});assert.equal(b.root.dataset.appearance,'cyber');b.choose('minimal');assert.equal(b.root.dataset.appearance,'minimal');});
test('invalid saved value never becomes a DOM theme',()=>{const b=boot({storage:new Map([['vico-web-appearance-v1','javascript:bad']])});assert.equal(b.root.dataset.appearance,'cyber');});
test('early head load reapplies states on DOMContentLoaded',()=>{const b=boot({loading:true});assert.ok(b.callbacks.DOMContentLoaded);b.callbacks.DOMContentLoaded();assert.equal(b.buttons[0].attrs['aria-pressed'],'true');});
test('unrelated click or disabled appearance does nothing',()=>{const b=boot();b.callbacks.click({target:{closest:()=>null}});b.buttons[1].disabled=true;b.choose('minimal');assert.equal(b.root.dataset.appearance,'cyber');assert.equal(b.storage.size,0);});
test('invalid appearance button does not write or change appearance',()=>{const b=boot();b.callbacks.click({target:{disabled:false,dataset:{appearanceChoice:'unsupported'},closest(){return this;}}});assert.equal(b.root.dataset.appearance,'cyber');assert.equal(b.storage.size,0);});
test('appearance code has no audio, network or route integration',()=>{assert.doesNotMatch(code,/\b(fetch|XMLHttpRequest|AudioContext|watchPosition|pushState|replaceState)\s*\(/);assert.doesNotMatch(code,/location\s*\.|from\s+['"].*(session|core|worklet)/);});
