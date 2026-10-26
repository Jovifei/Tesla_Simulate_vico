import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {ReferenceAuditionSession} from '../src/recorded-reference.mjs';

const pcm=Buffer.from('good');
const reference={schema:'vico.recorded.reference.v1',scope:'REFERENCE_ONLY',id:'hellcat-startup-public',
  title:'Hellcat startup public recording',file:'assets/recorded-references/hellcat.wav',
  sampleRate:48000,channels:1,frames:314306,sha256:createHash('sha256').update(pcm).digest('hex'),
  source:{author:'Axepas12',license:'CC BY-SA 4.0',licenseUrl:'https://creativecommons.org/licenses/by-sa/4.0/'},
  identity:{vehicle:'Dodge Challenger Hellcat',state:'UNKNOWN',synchronizedRpmLoad:false,OEMQualification:false},automaticLoop:false};
const source=(await readFile(new URL('../src/app.mjs',import.meta.url),'utf8'))
  .replace(/^import .*;$/mg,'').replace('import.meta.url',"'https://example.test/src/app.mjs'");

async function boot({fetchImpl=async()=>new Response(pcm)}={}){
  class Element{
    constructor(){this.hidden=false;this.value='';this.textContent='';this.dataset={};this.handlers={};this.children=[];this.classList={toggle(){}};this.disabled=false;}
    addEventListener(type,handler){this.handlers[type]=handler;}
    setAttribute(key,value){this[key]=value;}
    append(...items){this.children.push(...items);}
    replaceChildren(){this.children=[];}
  }
  const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const windowEvents={},documentEvents={},contexts=[],location={hash:'#/reference'};
  class Context{
    constructor(){this.currentTime=0;this.closed=0;this.sources=[];this.gains=[];contexts.push(this);}
    resume(){return Promise.resolve();}
    async decodeAudioData(){return {duration:314306/48000,numberOfChannels:1,sampleRate:48000};}
    createBufferSource(){const node={starts:0,stops:0,connect(){},disconnect(){},start(){this.starts++;},stop(){this.stops++;}};this.sources.push(node);return node;}
    createGain(){const node={gain:{value:1,setValueAtTime(){},linearRampToValueAtTime(){}},connect(){},disconnect(){}};this.gains.push(node);return node;}
    close(){this.closed++;return Promise.resolve();}
  }
  class Session extends ReferenceAuditionSession{constructor(options){super({...options,fetchImpl,createContext:()=>new Context()});}}
  const document={getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>[],
    addEventListener(type,handler){documentEvents[type]=handler;},hidden:false};
  const context=vm.createContext({document,window:{addEventListener(type,handler){windowEvents[type]=handler;},AudioContext:Context},
    location,navigator:{},ReferenceAuditionSession:Session,AudioSession:class{setInput(){}stop(){return Promise.resolve();}},
    loadCatalog:async()=>({vehicles:[],sourceCommit:'abc'}),loadRecordedReferenceCatalog:async()=>({references:[reference]}),
    GpsSpeedInput:class{},URL,performance:{now:()=>0},setTimeout,Blob,console,isSecureContext:true,crypto:globalThis.crypto,fetch:fetchImpl});
  await vm.runInContext(`(async()=>{${source}})()`,context);
  const card=get('reference-list').children[0];
  return {get,card,contexts,location,document,windowEvents,documentEvents,
    play:()=>card.children.find(x=>x.handlers.click).handlers.click()};
}

test('reference page plays only one real source and exposes bounded volume and stop',async()=>{
  const b=await boot();assert.equal(b.get('reference').hidden,false);
  await b.play();await b.play();
  assert.equal(b.contexts[0].sources[0].stops,1);assert.equal(b.contexts[0].closed,1);
  assert.equal(b.contexts[1].gains[1].gain.value,.2);
  b.get('reference-volume').value='0';b.get('reference-volume').handlers.input();
  assert.equal(b.contexts[1].gains[1].gain.value,0);
  b.get('reference-stop').handlers.click();assert.equal(b.contexts[1].sources[0].stops,1);
  assert.match(b.card.children.at(-1).textContent,/已停止/);
});

test('route, Escape, hidden visibility and pagehide stop reference source and close context',async()=>{
  for(const action of ['route','escape','hidden','pagehide']){
    const b=await boot();await b.play();
    if(action==='route'){b.location.hash='#/garage';await b.windowEvents.hashchange();}
    if(action==='escape')b.windowEvents.keydown({key:'Escape'});
    if(action==='hidden'){b.document.hidden=true;b.documentEvents.visibilitychange();}
    if(action==='pagehide')b.windowEvents.pagehide();
    assert.equal(b.contexts[0].sources[0].stops,1,action);assert.equal(b.contexts[0].closed,1,action);
  }
});

test('leaving during fetch prevents late real audio and stale playing status',async()=>{
  let resolve;const pending=new Promise(r=>resolve=r),b=await boot({fetchImpl:()=>pending});
  const playing=b.play();await Promise.resolve();
  b.location.hash='#/garage';await b.windowEvents.hashchange();resolve(new Response(pcm));await playing;
  assert.equal(b.contexts[0].sources.length,0);assert.equal(b.contexts[0].closed,1);
  assert.doesNotMatch(b.card.children.at(-1).textContent,/正在播放/);
});
