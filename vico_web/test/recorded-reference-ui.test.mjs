import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
const RecordedReferencePlayer=(await import('../src/recorded-reference.mjs')).RecordedReferencePlayer;

class Element {
  constructor() { this.hidden=false; this.textContent=''; this.dataset={}; this.handlers={}; this.children=[]; this.classList={toggle(){}}; this.disabled=false; }
  addEventListener(type, handler) { this.handlers[type]=handler; }
  setAttribute(key, value) { this[key]=value; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children=[]; }
}
const elements=new Map();
const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const events={};
const location={hash:'#/reference'};
const document={getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>[],addEventListener(){}};
const source=(await readFile(new URL('../src/app.mjs',import.meta.url),'utf8'))
  .replace(/^import .*;$/mg,'')
  .replace('import.meta.url',"'https://example.test/src/app.mjs'");
const catalog={vehicles:[],sourceCommit:'abc'};
const pcm=Buffer.from('good');
const references=[
  {schema:'vico.recorded.reference.v1',scope:'REFERENCE_ONLY',id:'hellcat-startup-public',title:'Hellcat startup public recording',file:'assets/recorded-references/hellcat.wav',sampleRate:48000,channels:1,frames:1,sha256:createHash('sha256').update(pcm).digest('hex'),source:{author:'Axepas12',license:'CC BY-SA 4.0',licenseUrl:'https://creativecommons.org/licenses/by-sa/4.0/'},identity:{vehicle:'Dodge Challenger Hellcat',state:'UNKNOWN',synchronizedRpmLoad:false,OEMQualification:false},automaticLoop:false}
];
class AudioContext{constructor(){}resume(){return Promise.resolve();}async decodeAudioData(){return {};}createBufferSource(){return {connect(){},start(){},loop:false};}close(){}}
const context=vm.createContext({document,window:{addEventListener(type,handler){events[type]=handler;},AudioContext},location,navigator:{},AudioSession:class{setInput(){}stop(){return Promise.resolve();}},loadCatalog:async()=>catalog,loadRecordedReferenceCatalog:async()=>({references}),GpsSpeedInput:class{},URL,performance:{now:()=>0},setInterval,clearInterval,setTimeout,Blob,console,isSecureContext:true,crypto:globalThis.crypto,fetch:async()=>new Response(pcm),AudioContext});
context.RecordedReferencePlayer=RecordedReferencePlayer;
context.document=document;
await vm.runInContext(`(async()=>{${source}})()`,context);
assert.equal(get('reference').hidden,false);
assert.equal(get('garage').hidden,true);
const card=get('reference-list').children[0];
assert.equal(card.dataset.id,'hellcat-startup-public');
const initialStatus=card.children.find(x=>x.textContent==='未校验');
assert.equal(initialStatus.textContent,'未校验');
const button=card.children.find(x=>x.handlers.click);
await button.handlers.click();
assert.equal(initialStatus.textContent,'SHA-256 已校验 · 正在播放真实 PCM，播完即停');
location.hash='#/garage';await events.hashchange();
assert.equal(get('reference').hidden,true);
assert.equal(get('garage').hidden,false);
