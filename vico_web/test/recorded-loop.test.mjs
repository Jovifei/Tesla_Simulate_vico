import test from 'node:test';
import assert from 'node:assert/strict';
import * as loop from '../src/recorded-loop.mjs';

const rate=8000;
const make=(seconds=4)=>Float32Array.from({length:seconds*rate},(_,i)=>Math.fround(.3*Math.sin(i*.023)+.1*Math.cos(i*.0041)));

test('long recorded cycle preserves stereo, source bytes, and every sample outside overlap',()=>{
  const left=make(),right=Float32Array.from(left,x=>-x/2),snapshots=[left.slice(),right.slice()];
  const result=loop.createRecordedCycle([left,right],rate,{startFrame:rate/2,endFrame:rate*4});
  assert.equal(result.crossfadeFrames,960);assert.equal(result.periodFrames,rate*3.5-960);
  assert.equal(result.sampleRate,rate);assert.equal(result.channels.length,2);
  assert.equal(result.periodSeconds,result.periodFrames/rate);
  for(let c=0;c<2;c++){
    assert.deepEqual([left,right][c],snapshots[c]);
    assert.deepEqual(result.channels[c].subarray(960),snapshots[c].subarray(rate/2+960,rate*4-960));
  }
});

test('crossfade is a convex complementary mix with continuous source boundary neighbors',()=>{
  const source=make(),{channels:[cycle],crossfadeFrames:f,periodFrames:n}=loop.createRecordedCycle([source],rate);
  assert.equal(cycle[0],source[source.length-f]);assert.equal(cycle[f-1],source[f-1]);
  assert.equal(cycle[f],source[f]);assert.equal(cycle[n-1],source[source.length-f-1]);
  for(let i=0;i<f;i++){
    const a=source[source.length-f+i],b=source[i];
    assert(cycle[i]>=Math.min(a,b)-1e-7&&cycle[i]<=Math.max(a,b)+1e-7);
  }
  assert.deepEqual(loop.createRecordedCycle([source],rate).channels[0],cycle);
});

test('DC and polarity retain fixed gain without equal-power correlated overshoot',()=>{
  for(const value of [.8,-.8,0]){
    const result=loop.createRecordedCycle([new Float32Array(3*rate).fill(value)],rate);
    for(const sample of result.channels[0])assert.equal(sample,Math.fround(value));
  }
});

test('subsecond and insufficient source regions are rejected instead of stretched',()=>{
  assert.throws(()=>loop.createRecordedCycle([make(2)],rate),/3.*30|region/i);
  assert.throws(()=>loop.createRecordedCycle([make(4)],rate,{startFrame:rate*2,endFrame:rate*4}),/3.*30|region/i);
  assert.throws(()=>loop.createRecordedCycle([new Float32Array(31*rate)],rate),/3.*30|region/i);
});

test('invalid PCM, sampling, and region inputs fail without silent repair or clipping',()=>{
  const a=make();
  for(const bad of [NaN,Infinity,-Infinity,1,-1]){
    const x=a.slice();x[rate]=bad;
    assert.throws(()=>loop.createRecordedCycle([x],rate),/finite|clip|PCM/i);
  }
  for(const channels of [[],[a,a.subarray(1)],[a,a,a],[[1,2]]])
    assert.throws(()=>loop.createRecordedCycle(channels,rate));
  for(const fs of [0,7999,48000.5,NaN,384000])assert.throws(()=>loop.createRecordedCycle([a],fs));
  for(const opts of [{startFrame:-1},{endFrame:a.length+1},{startFrame:1.5},{endFrame:rate}])
    assert.throws(()=>loop.createRecordedCycle([a],rate,opts));
});

test('device-resampled PCM retains natural sample clock at 44.1/48/96kHz',()=>{
  for(const sampleRate of [44100,48000,96000]){
    const input=new Float32Array(sampleRate*3).fill(.1);
    const result=loop.createRecordedCycle([input],sampleRate);
    assert.equal(result.periodFrames,input.length-Math.round(.12*sampleRate));
    assert.equal(result.periodSeconds,2.88);
  }
});
