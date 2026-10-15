import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

test('garage owns navigation, stop clears readouts, pedal stays demo-only, late selection cannot reopen cockpit',async()=>{
 const elements=new Map();
 class Element{constructor(){this.hidden=false;this.value='0';this.textContent='';this.dataset={};this.handlers={};this.children=[];this.classList={toggle(){}};}addEventListener(k,f){this.handlers[k]=f;}setAttribute(k,v){this[k]=v;}append(...x){this.children.push(...x);}replaceChildren(){this.children=[];}focus(){}setPointerCapture(){} }
 const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 let listener,stopResolve,deferStop=false;const events={};const location={hash:"#/garage"};const inputs=[];
 class AudioSession{constructor(base,cb){listener=cb;this.stage='idle';}setInput(x){inputs.push(x);}setVolume(){}start(){this.stage='running';listener({stage:'running'});}stop(){this.stage='idle';if(!deferStop)return Promise.resolve();deferStop=false;return new Promise(r=>{stopResolve=r;});}}
 const entry={id:'car',name:'Test car',kind:'V8',idleRpm:800,redlineRpm:8000};
 const document={getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>[],addEventListener(){},hidden:false};
 const source=(await readFile(new URL('../src/app.mjs',import.meta.url),'utf8')).replace(/^import .*;$/mg,'').replace('import.meta.url',"'https://example.test/src/app.mjs'");
 const context=vm.createContext({document,window:{addEventListener(k,f){events[k]=f;}},location,navigator:{},AudioSession,loadCatalog:async()=>({vehicles:[entry],sourceCommit:'abc'}),GpsSpeedInput:class{},URL,performance:{now:()=>0},setInterval,clearInterval,setTimeout,Blob,console,isSecureContext:true});
 await vm.runInContext(`(async()=>{${source}})()`,context);
 assert.equal(get('drive').hidden,true,'initial view must be garage');
 get('vehicles').children[0].handlers.click();await events.hashchange();
 assert.equal(get('redline-rpm').textContent,'8,000');assert.equal(get('garage').hidden,true);assert.equal(get('drive').hidden,false);
 get('start').handlers.click();listener({stage:'running',stats:{inputUsable:true,speedKmh:80,rpm:3000,gear:3,load:.5}});
 get('stop').handlers.click();assert.equal(get('speed').textContent,'000');assert.equal(get('rpm').textContent,'0');
 get('pedal').handlers.pointerdown({preventDefault(){},pointerId:1});assert.equal(inputs.at(-1).source,'demo');assert.equal(inputs.at(-1).scenario,'overspeed');
 await get('mode-manual').handlers.click();get('pedal').handlers.pointerup({pointerId:1});assert.equal(inputs.at(-1).source,'manual');
 deferStop=true;const pending=events.hashchange();get('back-garage').handlers.click();stopResolve();await pending;
 assert.equal(get('drive').hidden,true,'obsolete selection cannot reopen cockpit');
 listener({stage:'running',stats:{inputUsable:true,speedKmh:99,rpm:4000,gear:4,load:1}});assert.equal(get('speed').textContent,'000');
 location.hash='#/drive/unknown';await events.hashchange();assert.equal(get('garage').hidden,false);assert.match(get('garage-error').textContent,/未知/);
 location.hash='#/drive/car';await events.hashchange();assert.equal(get('drive').hidden,false);assert.equal(get('speed').textContent,'000');
 deferStop=true;const modeChange=get('mode-gps').handlers.click();assert.equal(get('start').disabled,true,'Start stays locked until AudioContext closes');stopResolve();await modeChange;assert.equal(get('start').disabled,false);assert.equal(get('speed').textContent,'—','GPS unknown must never look like measured zero');assert.equal(inputs.at(-1).source,'gps');assert.equal(inputs.at(-1).valid,false);
});
