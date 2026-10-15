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
