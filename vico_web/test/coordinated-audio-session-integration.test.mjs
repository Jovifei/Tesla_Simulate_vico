import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {AudioSession} from '../src/session.mjs';
import {fixtureBank,wav} from './fixtures.mjs';
import {coordinatedSyntheticFixture} from './coordinated-fixture.mjs';

const sha=x=>createHash('sha256').update(x).digest('hex');
function server({bankRate=48000}={}){
 const bank=fixtureBank({constant:true,count:256}),files=new Map();
 const asset=samples=>{
  const bytes=wav(samples,bankRate),hash=sha(bytes);
  files.set('/banks/hellcat_v6/asset-'+hash+'.wav',bytes);
  return {file:'asset-'+hash+'.wav',sha256:hash,bytes:bytes.length};
 };
 const loops=bank.loops.map(({rpm,load,samples})=>({rpm,load,...asset(samples)}));
 const afterfire=asset(bank.afterfire);
 const shifts=bank.shifts.map(asset);
 const descriptor={schema:'vico.web.bank.v1',vehicleKey:'hellcat_v6',
  sampleRate:bankRate,spec:bank.spec,sourceCommit:'test-only',
  normalIdentity:'legacy_unmodified',referenceManifestSha256:'a'.repeat(64),
  loops,afterfire,shifts};
 const json=Buffer.from(JSON.stringify(descriptor));
 files.set('/banks/hellcat_v6/bank.json',json);
 return {files,entry:{id:'hellcat_v6',name:'Test Hellcat',bankFile:'banks/hellcat_v6/bank.json',bankSha256:sha(json)}};
}
function globals({deviceRate=48000}={}){
 const backup=new Map(),set=(key,value)=>{backup.set(key,{own:Object.hasOwn(globalThis,key),value:globalThis[key]});Object.defineProperty(globalThis,key,{configurable:true,writable:true,value});};
 const contexts=[],nodes=[];
 class Ctx{
  constructor(){this.state='suspended';this.sampleRate=deviceRate;this.currentTime=0;this.destination={};this.audioWorklet={addModule:async()=>{}};contexts.push(this);}
  async resume(){this.state='running';}
  createGain(){return {gain:{value:0,setTargetAtTime(){}},connect(){return this}};}
  async close(){this.state='closed';}
 }
 class Node{
  constructor(ctx){this.ctx=ctx;this.sent=[];nodes.push(this);
   this.port={onmessage:null,postMessage:(m,transfer)=>{
    this.sent.push({m,transfer});
    if(m.type==='init')queueMicrotask(()=>this.port.onmessage({data:{type:'ready'}}));
   }};
  }
  connect(){return {connect(){}}}
  disconnect(){}
 }
 set('AudioContext',Ctx);set('AudioWorkletNode',Node);set('isSecureContext',true);
 return {contexts,nodes,restore:()=>{
  for(const [key,old] of backup){if(old.own)Object.defineProperty(globalThis,key,{configurable:true,writable:true,value:old.value});else delete globalThis[key];}
 }};
}

test('actual session.start transfers verified owned synthetic F32LE and closes on stop',async()=>{
 const {files,entry}=server(),env=globals();
 const oldFetch=globalThis.fetch;
 globalThis.fetch=async input=>{
  const path=new URL(input.toString()).pathname,bytes=files.get(path);
  return bytes?new Response(bytes):new Response('missing',{status:404});
 };
 const candidate=coordinatedSyntheticFixture(),original=candidate.samples[4000];
 try{
  const s=new AudioSession(new URL('https://example.invalid/'));
  await s.start(entry,'NORMAL_SEAM_ENVELOPE_V1',{source:'demo',scenario:'cruise'},{recordedCandidate:candidate});
  assert.equal(s.stage,'running',s.last?.message||'session never entered running');
  assert.equal(env.contexts.length,1);
  assert.equal(env.nodes.length,1);
  const init=env.nodes[0].sent.find(x=>x.m.type==='init');
  assert.ok(init);
  assert.equal(init.m.recordedVerified,true);
  assert.notEqual(init.m.recordedCandidate.samples,candidate.samples);
  assert.equal(sha(Buffer.from(init.m.recordedCandidate.samples.buffer)),candidate.pcmSha256);
  assert.equal(init.m.recordedCandidate.evidence.sourceClass,'SYNTHETIC_TEST_ONLY');
  assert(init.transfer.includes(init.m.recordedCandidate.samples.buffer));
  assert.equal(candidate.samples[4000],original);
  await s.stop(true);
  assert.equal(s.stage,'idle');
  assert.equal(env.contexts[0].state,'closed');
 }finally{env.restore();globalThis.fetch=oldFetch;}
});

test('invalid full source SHA fails closed before Worklet init',async()=>{
 const {files,entry}=server(),env=globals(),oldFetch=globalThis.fetch;
 globalThis.fetch=async input=>{
  const bytes=files.get(new URL(input.toString()).pathname);
  return bytes?new Response(bytes):new Response('missing',{status:404});
 };
 const candidate=coordinatedSyntheticFixture();
 candidate.samples[7000]=.22;
 try{
  const s=new AudioSession(new URL('https://example.invalid/'));
  await s.start(entry,'NORMAL_SEAM_ENVELOPE_V1',{source:'demo',scenario:'stop'},{recordedCandidate:candidate});
  assert.equal(s.stage,'error');
  assert.equal(env.nodes.length,0);
  assert(env.contexts.every(x=>x.state==='closed'));
 }finally{env.restore();globalThis.fetch=oldFetch;}
});

test('session rejects source and internal renderer rate mismatch before Worklet creation',async()=>{
 const {files,entry}=server({bankRate:96000}),env=globals(),oldFetch=globalThis.fetch;
 globalThis.fetch=async input=>{
  const bytes=files.get(new URL(input.toString()).pathname);
  return bytes?new Response(bytes):new Response('missing',{status:404});
 };
 const s=new AudioSession(new URL('https://example.invalid/'));
 try{
  await s.start(entry,'NORMAL_SEAM_ENVELOPE_V1',{source:'demo',scenario:'stop'},
   {recordedCandidate:coordinatedSyntheticFixture()});
  assert.equal(s.stage,'error');
  assert.equal(env.nodes.length,0);
  assert(env.contexts.every(x=>x.state==='closed'));
 }finally{await s.stop(true);env.restore();globalThis.fetch=oldFetch;}
});

test('48k source and renderer remain usable with 44.1k and 96k output contexts',async()=>{
 for(const deviceRate of [44100,96000]){
  const {files,entry}=server(),env=globals({deviceRate}),oldFetch=globalThis.fetch;
  globalThis.fetch=async input=>{
   const bytes=files.get(new URL(input.toString()).pathname);
   return bytes?new Response(bytes):new Response('missing',{status:404});
  };
  const s=new AudioSession(new URL('https://example.invalid/'));
  try{
   await s.start(entry,'NORMAL_SEAM_ENVELOPE_V1',{source:'demo',scenario:'stop'},
    {recordedCandidate:coordinatedSyntheticFixture()});
   assert.equal(s.stage,'running');
   assert.equal(env.contexts[0].sampleRate,deviceRate);
   assert.equal(env.nodes[0].sent.find(x=>x.m.type==='init').m.bank.sampleRate,48000);
  }finally{await s.stop(true);env.restore();globalThis.fetch=oldFetch;}
 }
});
