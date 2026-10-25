import test from 'node:test';
import assert from 'node:assert/strict';
import {fixtureBank} from './fixtures.mjs';
import {coordinatedSyntheticFixture} from './coordinated-fixture.mjs';

let Processor;
globalThis.sampleRate=48000;
globalThis.AudioWorkletProcessor=class{
 constructor(){
  this.messages=[];
  this.port={onmessage:null,postMessage:m=>this.messages.push(m)};
 }
};
globalThis.registerProcessor=(_,type)=>{Processor=type;};
await import('../src/worklet.mjs');

function init({candidate=coordinatedSyntheticFixture(),verified=true,mode='NORMAL_SEAM_ENVELOPE_V1',bankVehicle='hellcat_v6'}={}){
 const p=new Processor(),bank={...fixtureBank({constant:true}),vehicleKey:bankVehicle};
 p.port.onmessage({data:{type:'init',owner:21,bank,mode,
  input:{source:'demo',scenario:'cruise'},recordedCandidate:candidate,recordedVerified:verified}});
 return p;
}
function frames(p,at=0,count=12000) {
 const out=new Float32Array(count);
 for(let i=0;i<count;){
  if(i%9600===0)p.port.onmessage({data:{type:'heartbeat',owner:21}});
  const block=Math.min(i%2?257:128,count-i);
  const channel=new Float32Array(block);
  p.process([],[[channel]]);
  out.set(channel,i);i+=block;
 }
 return out;
}

test('real AudioWorklet init routes opt-in coordinated source, not generic bank replay',()=>{
 const p=init(),out=frames(p);
 assert(!p.failed);
 assert(p.engine.recorded);
 assert(out.some(x=>Math.abs(x)>.005));
 assert.equal(p.engine.snapshot().coordinatedVoice.sourceKind,'SYNTHETIC_TEST_ONLY');
 assert.equal(p.engine.snapshot().coordinatedVoice.renderedFrames,out.length);
 assert(out.every(x=>Number.isFinite(x)&&Math.abs(x)<.84139515));
});

test('worklet rejects tampered source eligibility and has only zero output on error',()=>{
 for(const patch of [
  {verified:false},
  {mode:'LEGACY_LOCKED'},
  {bankVehicle:'ferrari_458'},
  {candidate:{...coordinatedSyntheticFixture(),evidence:{sourceClass:'PRIVATE_UNALIGNED'}}}
 ]){
  const p=init(patch);
  assert.equal(p.failed,true);
  assert(p.messages.some(m=>m.type==='error'));
  const x=new Float32Array(257).fill(.8);
  p.process([],[[x]]);
  assert(x.every(v=>v===0));
 }
});

test('muted/unknown GPS source cancels only the explicit synthetic voice owner',()=>{
 const p=init();
 frames(p,0,3500);
 const before=p.engine.snapshot().coordinatedVoice.renderedFrames;
 p.port.onmessage({data:{type:'input',owner:21,source:'gps',valid:false}});
 frames(p,0,12000);
 assert.equal(p.engine.snapshot().coordinatedVoice.renderedFrames,before);
 assert(p.engine.snapshot().coordinatedVoice.cancelled);
 assert.equal(p.engine.snapshot().inputUsable,false);
 p.port.onmessage({data:{type:'input',owner:21,source:'demo',scenario:'launch'}});
 frames(p,0,5000);
 assert.equal(p.engine.snapshot().coordinatedVoice.renderedFrames,before);
 p.port.onmessage({data:{type:'stop',owner:21}});
 frames(p,0,46000);
 assert(p.engine.stopped);
 assert(!p.failed);
});

test('legacy sample path remains untouched when no candidate is provided',()=>{
 const bank={...fixtureBank({constant:true}),vehicleKey:'hellcat_v6'};
 const p=new Processor();
 p.port.onmessage({data:{type:'init',owner:21,bank,mode:'NORMAL_SEAM_ENVELOPE_V1',
  input:{source:'demo',scenario:'stop'}}});
 assert(!p.failed);
 const x=frames(p,0,1000);
 assert(x.every(v=>Number.isFinite(v)));
 assert.equal(p.engine.recorded,null);
 assert.equal(p.engine.snapshot().coordinatedVoice,undefined);
});

test('device output rate conversion preserves the 48k coordinated model clock',()=>{
 try{
  for(const rate of [44100,96000]){
   globalThis.sampleRate=rate;
   const p=init(),output=frames(p,0,Math.round(rate*.1));
   assert(!p.failed);
   assert(output.every(v=>Number.isFinite(v)&&Math.abs(v)<.84139515));
   const rendered=p.engine.snapshot().coordinatedVoice.renderedFrames;
   assert(Math.abs(rendered/48000-.1)<=3/48000,`device ${rate}: ${rendered} internal frames`);
  }
 }finally{globalThis.sampleRate=48000;}
});
