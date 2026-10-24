import test from 'node:test';
import assert from 'node:assert/strict';
import {LiveEngine} from '../src/core.mjs';
import {fixtureBank} from './fixtures.mjs';

const withStart=()=>({...fixtureBank({constant:true}),startup:{samples:new Float32Array(48000).fill(.6),sampleRate:48000,sha256:'a'.repeat(64),handoffMs:150,fadeInMs:5}});
function frames(engine,n){const x=new Float32Array(n);for(let i=0;i<n;i++){if(engine.frame%9600===0)engine.command({type:'heartbeat'});x[i]=engine.next();}return x;}

test('normal start plays a separate start segment before idle, then hands off once',()=>{
  const e=new LiveEngine(withStart(),'NORMAL_SEAM_ENVELOPE_V1',7);
  const x=frames(e,24000);assert(x[12000]>.5);
  assert(e.snapshot().outputPreClipPeak>.5);
  assert.equal(e.snapshot().startup.stage,'playing');
  frames(e,48000);assert.equal(e.snapshot().startup.stage,'ended');
  assert(e.next()<.3);assert.equal(e.snapshot().startup.outputFrames,48000);
});
test('demo demand waits for ignition instead of accelerating a stopped crank',()=>{
  const e=new LiveEngine(withStart(),'NORMAL_SEAM_ENVELOPE_V1',7);
  e.command({type:'input',source:'demo',scenario:'launch'});
  frames(e,24000);assert.equal(e.snapshot().speedKmh,0);
  frames(e,48000);assert(e.snapshot().speedKmh>0);
});
test('legacy reference ignores new startup asset byte for byte',()=>{
  const a=new LiveEngine(withStart(),'LEGACY_LOCKED',7),b=new LiveEngine(fixtureBank({constant:true}),'LEGACY_LOCKED',7);
  assert.deepEqual(frames(a,24000),frames(b,24000));
});
test('invalid GPS never plays the starter and cannot resurrect it when GPS resumes',()=>{
  const e=new LiveEngine(withStart(),'NORMAL_SEAM_ENVELOPE_V1',7);
  e.command({type:'input',source:'gps',valid:false});
  assert(frames(e,12000).every(x=>x===0));
  assert.equal(e.snapshot().startup.stage,'cancelled');
  e.command({type:'input',source:'gps',valid:true,speedKmh:40,accelMps2:0,ageMs:0});
  const x=frames(e,12000);assert(x.at(-1)<.3);
  assert.equal(e.snapshot().startup.stage,'cancelled');
});
test('stop cancels the one-shot immediately and leaves only the existing bounded continuous fade',()=>{
  const e=new LiveEngine(withStart(),'NORMAL_SEAM_ENVELOPE_V1',7);
  frames(e,12000);e.command({type:'stop'});
  assert.equal(e.snapshot().startup.stage,'cancelled');
  const x=frames(e,24000);assert(x.every(v=>Math.abs(v)<.3));assert(e.stopped);
});
