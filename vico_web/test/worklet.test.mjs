import test from 'node:test';import assert from 'node:assert/strict';import {fixtureBank} from './fixtures.mjs';
let Processor;
globalThis.sampleRate=48000;
globalThis.AudioWorkletProcessor=class {constructor(){this.messages=[];this.port={postMessage:m=>this.messages.push(m),onmessage:null};}};
globalThis.registerProcessor=(name,ctor)=>{assert.equal(name,'vico-bank');Processor=ctor;};
await import('../src/worklet.mjs');
function init(rate=48000){globalThis.sampleRate=rate;const p=new Processor();p.port.onmessage({data:{type:'init',owner:7,bank:fixtureBank(),mode:'NORMAL_SEAM_ENVELOPE_V1'}});assert.equal(p.messages[0].type,'ready');return p;}
test('actual worklet process entry generates PCM and diagnostics at arbitrary quantum lengths',()=>{for(const rate of [44100,48000,96000]){const p=init(rate);p.port.onmessage({data:{type:'input',owner:7,source:'demo',scenario:'launch'}});let peak=0;for(let b=0;b<120;b++){const out=new Float32Array(b%2?128:256);p.process([],[[out]]);out.forEach(x=>peak=Math.max(peak,Math.abs(x)));}assert(peak>0);assert(p.messages.some(m=>m.type==='stats'&&m.stats.frames>0));assert(!p.failed);}});
test('worklet ignores obsolete control owners and stops on explicit stop',()=>{const p=init();p.port.onmessage({data:{type:'input',owner:6,source:'demo',scenario:'overspeed'}});assert.equal(p.engine.scenario,'stop');p.port.onmessage({data:{type:'stop'}});for(let i=0;i<200;i++)p.process([],[[new Float32Array(128)]]);assert(p.engine.stopped);});
test('worklet protocol error is visible and output silences, not false PASS',()=>{const p=init();p.port.onmessage({data:{type:'input',owner:7,source:'invalid'}});const out=new Float32Array(128).fill(1);p.process([],[[out]]);assert(out.every(v=>v===0));assert(p.messages.some(m=>m.type==='error'));});
test('synthetic four-input frame crosses the worklet atomically and invalid input silences it',()=>{
 const p=init();p.port.onmessage({data:{type:'input',owner:7,source:'v14_fixture',scope:'SYNTHETIC_ONLY',throttle:.3,rpm:2200,load:.5,gear:0}});
 p.process([],[[new Float32Array(128)]]);assert.deepEqual([p.engine.state.throttle,p.engine.state.rpm,p.engine.state.load,p.engine.state.gear],[.3,2200,.5,0]);
 p.port.onmessage({data:{type:'input',owner:7,source:'v14_fixture',scope:'SYNTHETIC_ONLY',throttle:.9,rpm:2300,load:2,gear:1}});
 const out=new Float32Array(128).fill(1);p.process([],[[out]]);assert(out.every(x=>x===0));assert(p.messages.some(m=>m.type==='error'));
});
test('synthetic fixture produces finite PCM on the same worklet, then stale GPS silences it',()=>{
 const p=init(),owner=p.engine;
 p.port.onmessage({data:{type:'input',owner:7,source:'v14_fixture',scope:'SYNTHETIC_ONLY',throttle:.4,rpm:2300,load:.5,gear:2}});
 let peak=0;
 for(let i=0;i<100;i++){if(i%20===0)p.port.onmessage({data:{type:'heartbeat',owner:7}});const out=new Float32Array(128);p.process([],[[out]]);assert(out.every(Number.isFinite));for(const x of out)peak=Math.max(peak,Math.abs(x));}
 assert(peak>0);assert.equal(p.engine,owner);
 const stats=p.messages.findLast(m=>m.type==='stats').stats;assert.deepEqual([stats.throttle,stats.rpm,stats.load,stats.gear],[.4,2300,.5,2]);
 p.port.onmessage({data:{type:'input',owner:7,source:'gps',valid:true,speedKmh:20,accelMps2:0,ageMs:1950}});
 let last;
 for(let i=0;i<220;i++){if(i%20===0)p.port.onmessage({data:{type:'heartbeat',owner:7}});last=new Float32Array(128);p.process([],[[last]]);}
 assert.equal(p.engine,owner);assert.equal(p.engine.snapshot().inputUsable,false);assert(last.every(x=>x===0));
});
