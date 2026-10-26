import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import * as audio from '../src/recorded-reference.mjs';

const bytes=Buffer.from('verified-pcm');
const reference={schema:'vico.recorded.reference.v1',scope:'REFERENCE_ONLY',id:'reference-take',
  file:'assets/take.wav',sampleRate:24000,channels:2,frames:240000,automaticLoop:false,
  sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length,
  source:{author:'Recorder',license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/'},
  identity:{vehicle:'SRT version unknown',state:'UNKNOWN',synchronizedRpmLoad:false,OEMQualification:false}};
const deferred=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve};};
function pcmBuffer(rate=48000){
  const channels=[new Float32Array(rate*10).fill(.2),new Float32Array(rate*10).fill(-.1)];
  return {duration:10,length:rate*10,sampleRate:rate,numberOfChannels:2,getChannelData:i=>channels[i]};
}
function setup({fetchImpl=async()=>new Response(bytes),decode=null,resume=null}={}){
  const contexts=[],events=[];
  class Context{
    constructor(){this.currentTime=0;this.sampleRate=48000;this.closed=0;this.sources=[];this.destination={};this.gains=[];contexts.push(this);}
    resume(){return resume?.promise??Promise.resolve();}
    decodeAudioData(){if(decode?.error)throw decode.error;return decode?.promise??Promise.resolve(pcmBuffer());}
    createBuffer(channels,length,sampleRate){const data=Array.from({length:channels},()=>new Float32Array(length));
      return {length,sampleRate,numberOfChannels:channels,duration:length/sampleRate,getChannelData:i=>data[i],copyToChannel:(values,i)=>data[i].set(values)};}
    createGain(){const calls=[],gain={value:1,setValueAtTime(...a){calls.push(['set',...a]);},linearRampToValueAtTime(...a){calls.push(['ramp',...a]);},cancelScheduledValues(){}};
      const node={gain,calls,connect(){return this;},disconnect(){}};this.gains.push(node);return node;}
    createBufferSource(){const source={loop:true,starts:[],stops:0,connect(){return this;},disconnect(){},start(...args){this.starts.push(args);},stop(){this.stops++;}};this.sources.push(source);return source;}
    close(){this.closed++;return Promise.resolve();}
  }
  assert.equal(typeof audio.ReferenceAuditionSession,'function','an owned real-audio playback session is required');
  const session=new audio.ReferenceAuditionSession({base:new URL('https://example.test/'),fetchImpl,
    createContext:()=>new Context(),onChange:event=>events.push(event)});
  return {session,contexts,events};
}

test('replacement owns one source, uses bounded gain, ramps, and source seconds after resampling',async()=>{
  const {session,contexts,events}=setup();
  await session.play(reference,{startSeconds:2,endSeconds:5});
  const first=contexts[0];assert.deepEqual(first.sources[0].starts,[[0,2,3]]);
  assert.equal(first.sources[0].loop,false);assert.equal(first.gains[1].gain.value,.2);
  assert(first.gains[0].calls.some(x=>x[0]==='set'&&x[1]===0&&x[2]===0));
  assert(first.gains[0].calls.some(x=>x[0]==='ramp'&&x[1]===1&&x[2]===.008));
  assert(first.gains[0].calls.some(x=>x[0]==='ramp'&&x[1]===0&&x[2]===3));
  session.setVolume(12);assert.equal(session.volume,.7);
  session.setVolume(0);assert.equal(first.gains[1].gain.value,0);
  await session.play(reference);assert.equal(first.sources[0].stops,1);assert.equal(first.closed,1);
  assert.equal(contexts.length,2);first.sources[0].onended?.();
  assert.equal(events.at(-1).stage,'playing','obsolete ended cannot end new owner');
  session.stop();assert.equal(contexts[1].sources[0].stops,1);assert.equal(contexts[1].closed,1);
  session.stop();assert.equal(contexts[1].closed,1);assert.equal(events.at(-1).stage,'stopped');
});

test('stop cancels held download and no late body starts reference audio',async()=>{
  const held=deferred();let signal;const {session,contexts}=setup({fetchImpl:(url,options)=>{signal=options.signal;return held.promise;}});
  const playing=session.play(reference);await Promise.resolve();session.stop();
  assert.equal(signal.aborted,true);held.resolve(new Response(bytes));await playing;
  assert.equal(contexts[0].sources.length,0);assert.equal(contexts[0].closed,1);
});

test('stop during decode or resume cannot resurrect playback',async()=>{
  for(const boundary of ['decode','resume']){
    const held=deferred(),reached=deferred();const b=setup({[boundary]:held});
    if(boundary==='decode'){
      const original=b.session.createContext;
      b.session.createContext=()=>{const ctx=original();ctx.decodeAudioData=()=>{reached.resolve();return held.promise;};return ctx;};
    }
    const playing=b.session.play(reference);
    if(boundary==='decode')await reached.promise;else await Promise.resolve();
    b.session.stop();held.resolve({duration:10,sampleRate:48000,length:480000,numberOfChannels:2});await playing;
    assert.equal(b.contexts[0].sources.length,0);assert.equal(b.contexts[0].closed,1);
  }
});

test('natural end and decode failure close exactly once and report actual state',async()=>{
  const good=setup();await good.session.play(reference);good.contexts[0].sources[0].onended();
  assert.equal(good.contexts[0].closed,1);assert.equal(good.events.at(-1).stage,'ended');
  good.session.stop();assert.equal(good.contexts[0].closed,1);
  const bad=setup({decode:{error:new Error('decode failed')}});
  await assert.rejects(bad.session.play(reference),/decode failed/);
  assert.equal(bad.contexts[0].closed,1);assert.equal(bad.events.at(-1).stage,'error');
});

test('invalid segment, tampered content and decoded format mismatch never create a source',async()=>{
  const b=setup();await assert.rejects(b.session.play(reference,{startSeconds:9,endSeconds:11}),/segment/);
  assert.equal(b.contexts.length,0);
  const wrong=setup({fetchImpl:async()=>new Response(Buffer.from('wrong'))});
  await assert.rejects(wrong.session.play(reference),/length|SHA-256/);assert.equal(wrong.contexts[0].sources.length,0);
  const mismatch=setup({decode:{promise:Promise.resolve({duration:9,length:432000,sampleRate:48000,numberOfChannels:2})}});
  await assert.rejects(mismatch.session.play(reference),/duration|format/);assert.equal(mismatch.contexts[0].sources.length,0);
});

test('a new owner survives completion of an obsolete download or decode',async()=>{
  for(const boundary of ['download','decode']){
    const held=deferred(),reached=deferred();let loads=0;
    const b=setup({fetchImpl:()=>++loads===1&&boundary==='download'?held.promise:Promise.resolve(new Response(bytes))});
    if(boundary==='decode'){
      const make=b.session.createContext;let index=0;
      b.session.createContext=()=>{const ctx=make();if(index++===0)ctx.decodeAudioData=()=>{reached.resolve();return held.promise;};return ctx;};
    }
    const old=b.session.play(reference);
    if(boundary==='decode')await reached.promise;else await Promise.resolve();
    await b.session.play({...reference,id:'replacement-take'});
    held.resolve(boundary==='download'?new Response(bytes):{duration:10,sampleRate:48000,length:480000,numberOfChannels:2});
    await old;
    assert.equal(b.contexts[0].sources.length,0);assert.equal(b.contexts[0].closed,1);
    assert.equal(b.contexts[1].sources[0].starts.length,1);assert.equal(b.events.at(-1).id,'replacement-take');
    b.session.stop();
  }
});

test('resume rejection reports error and releases context',async()=>{
  const b=setup(),make=b.session.createContext;
  b.session.createContext=()=>{const ctx=make();ctx.resume=()=>Promise.reject(new Error('resume denied'));return ctx;};
  await assert.rejects(b.session.play(reference),/resume denied/);
  assert.equal(b.contexts[0].closed,1);assert.equal(b.events.at(-1).stage,'error');
});

test('explicit sustain is a natural-rate stereo long cycle bounded to sixty seconds and one owner',async()=>{
  const {session,contexts,events}=setup();
  await session.play(reference,{startSeconds:2,endSeconds:5,sustain:true});
  const ctx=contexts[0],source=ctx.sources[0];
  assert.equal(source.loop,true);assert.deepEqual(source.starts,[[0,0,60]]);
  assert.equal(source.buffer.numberOfChannels,2);assert.equal(source.buffer.sampleRate,48000);
  assert.equal(source.buffer.length,Math.round(2.88*48000));
  assert.equal(source.loopStart,0);assert.equal(source.loopEnd,source.buffer.duration);
  assert.equal(source.buffer.getChannelData(0)[12000],Math.fround(.2));
  assert.equal(source.buffer.getChannelData(1)[12000],Math.fround(-.1));
  assert.equal(events.at(-1).sustain,true);assert.equal(events.at(-1).durationSeconds,60);
  assert.equal(events.at(-1).periodSeconds,2.88);
  assert(ctx.gains[0].calls.some(x=>x[0]==='ramp'&&x[1]===0&&x[2]===60));
  source.onended();assert.equal(ctx.closed,1);assert.equal(events.at(-1).stage,'ended');
});

test('sustain rejects short selections, excessive spans or non-boolean activation before audio starts',async()=>{
  for(const options of [{startSeconds:0,endSeconds:2,sustain:true},{sustain:'true'}]){
    const b=setup();await assert.rejects(b.session.play(reference,options),/sustain|3.*30|region/i);
    assert.equal(b.contexts.length,0);
  }
});

test('sustain uses decoded device sample rate and stops during download without resurrection',async()=>{
  for(const rate of [44100,96000]){
    const b=setup({decode:{promise:Promise.resolve(pcmBuffer(rate))}});
    await b.session.play(reference,{startSeconds:2,endSeconds:5,sustain:true});
    const s=b.contexts[0].sources[0];assert.equal(s.buffer.sampleRate,rate);assert.equal(s.buffer.duration,2.88);
    b.session.setVolume(0);assert.equal(b.contexts[0].gains[1].gain.value,0);
    b.session.stop();assert.equal(s.stops,1);assert.equal(b.contexts[0].closed,1);
  }
  const held=deferred(),b=setup({fetchImpl:()=>held.promise});
  const pending=b.session.play(reference,{sustain:true});await Promise.resolve();b.session.stop();
  held.resolve(new Response(bytes));assert.equal(await pending,false);assert.equal(b.contexts[0].sources.length,0);
});

test('clipped recording cannot enter sustain and failure cleans ownership',async()=>{
  const buffer=pcmBuffer();buffer.getChannelData(0)[200000]=1;
  const b=setup({decode:{promise:Promise.resolve(buffer)}});
  await assert.rejects(b.session.play(reference,{sustain:true}),/clipped/);
  assert.equal(b.contexts[0].closed,1);assert.equal(b.contexts[0].sources.length,0);
  assert.equal(b.events.at(-1).stage,'error');
});
