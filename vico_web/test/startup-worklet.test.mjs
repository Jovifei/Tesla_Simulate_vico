import test from 'node:test';
import assert from 'node:assert/strict';
import {fixtureBank} from './fixtures.mjs';
let Processor;
globalThis.sampleRate=48000;
globalThis.AudioWorkletProcessor=class{constructor(){this.messages=[];this.port={onmessage:null,postMessage:m=>this.messages.push(m)};}};
globalThis.registerProcessor=(_name,ctor)=>{Processor=ctor;};
await import('../src/worklet.mjs');
const bank=()=>({...fixtureBank({constant:true}),startup:{samples:new Float32Array(48000).fill(.6),sampleRate:48000,sha256:'a'.repeat(64),fadeInMs:5,handoffMs:150}});
test('initial invalid GPS is applied atomically before the worklet can emit starter audio',()=>{
  const p=new Processor();p.port.onmessage({data:{type:'init',owner:7,bank:bank(),mode:'NORMAL_SEAM_ENVELOPE_V1',input:{source:'gps',valid:false}}});
  const out=new Float32Array(128);p.process([],[[out]]);
  assert(out.every(x=>x===0));assert.equal(p.engine.source,'gps');
  assert.equal(p.engine.snapshot().startup.stage,'cancelled');
});
test('actual worklet startup PCM and output diagnostics survive host quantum and rate changes',()=>{
  for(const rate of [44100,48000,96000]){
    globalThis.sampleRate=rate;const p=new Processor();
    p.port.onmessage({data:{type:'init',owner:7,bank:bank(),mode:'NORMAL_SEAM_ENVELOPE_V1',input:{source:'demo',scenario:'stop'}}});
    let peak=0;
    for(let b=0;b<100;b++){const x=new Float32Array(b%2?128:257);p.process([],[[x]]);for(const v of x){assert(Number.isFinite(v));peak=Math.max(peak,Math.abs(v));}}
    assert(peak>.3);assert.equal(p.engine.snapshot().startup.owner,7);
    assert.equal(p.engine.snapshot().outputAboveContractFrames,0);assert(!p.failed);
  }
});
