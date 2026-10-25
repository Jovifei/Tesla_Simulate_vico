import test from 'node:test';
import assert from 'node:assert/strict';
import {CoordinatedLongTakeVoice,validateLongTake} from '../src/coordinated-longtake.mjs';
import {BankRenderer,LiveEngine,PEAK_CONTRACT} from '../src/core.mjs';
import {fixtureBank,state} from './fixtures.mjs';
import {coordinatedSyntheticFixture} from './coordinated-fixture.mjs';

function voice(){return new CoordinatedLongTakeVoice(coordinatedSyntheticFixture(),{alreadyVerified:true});}
function pcm(v,n){const out=new Float32Array(n);for(let i=0;i<n;i++)out[i]=v.next();return out;}
function live(c,enabled=true){
 const bank={...fixtureBank({constant:true}),vehicleKey:'hellcat_v6'};
 return new LiveEngine(bank,'NORMAL_SEAM_ENVELOPE_V1',13,
  enabled?{recordedCandidate:c,recordedVerified:true}:{});
}
function stream(engine,n,events=[]){
 const out=new Float32Array(n);
 let block=0;
 for(let i=0;i<n;i++){
  if(i%9600===0)engine.command({type:'heartbeat'});
  if(events.length && i===events[block]?.frame){
   engine.command({type:'input',source:'demo',scenario:events[block].scenario});block++;
  }
  out[i]=engine.next();
 }
 return out;
}

test('coordinated source rejects a mismatched internal bank rate without restricting legacy banks',()=>{
 const candidate=coordinatedSyntheticFixture();
 const bank={...fixtureBank({constant:true}),vehicleKey:'hellcat_v6',sampleRate:96000};
 assert.throws(()=>new LiveEngine(bank,'NORMAL_SEAM_ENVELOPE_V1',13,
  {recordedCandidate:candidate,recordedVerified:true}),/sample rate/i);
 assert.doesNotThrow(()=>new LiveEngine(bank,'NORMAL_SEAM_ENVELOPE_V1',13));
});
test('finite phase-complete single-take windows and explicit licence/state/phase gate',()=>{
 const c=coordinatedSyntheticFixture();
 assert.equal(validateLongTake(c).regionCount,2);
 assert.throws(()=>new CoordinatedLongTakeVoice(c),/SHA.*verified/);
 for(const patch of [
  {...c,vehicleKey:'ferrari_458'}, {...c,pcmSha256:'broken'},
  {...c,regions:[c.regions[0]]},
  {...c,evidence:{...c.evidence,sourceClass:'PRIVATE_UNALIGNED'}},
  {...c,evidence:{...c.evidence,licenseGate:'PRODUCT_DISTRIBUTION_CLEARED'}},
  {...c,regions:[c.regions[0],{...c.regions[1],startFrame:100}]},
  {...c,regions:[c.regions[0],{...c.regions[1],cycles720:16}]},
  {...c,regions:[c.regions[0],{...c.regions[1],referenceRpm:900}]},
  {...c,samples:Float32Array.from(c.samples,v=>v)}
 ]) {
  // Valid cloned PCM is handled by byte verification, not rejected merely for cloning.
  if(patch.samples!==undefined&&patch.samples!==c.samples){assert.equal(validateLongTake(patch).regionCount,2);continue;}
  assert.throws(()=>validateLongTake(patch));
 }
 const nan=coordinatedSyntheticFixture();nan.samples[90000]=NaN;
 assert.throws(()=>validateLongTake(nan),/source PCM/);
 const clipped=coordinatedSyntheticFixture();clipped.samples[90000]=.75;
 assert.throws(()=>validateLongTake(clipped),/source PCM/);
 const seam=coordinatedSyntheticFixture();seam.samples[95999]=-.5;
 assert.throws(()=>validateLongTake(seam),/boundary/);
});

test('same-take phase advances across arbitrary PCM quantum partitions without resets',()=>{
 const a=voice(),b=voice();a.setControl(960,.3);b.setControl(960,.3);
 const expected=pcm(a,43000),actual=new Float32Array(43000);
 for(let at=0,i=0;at<actual.length;i++){const n=Math.min([1,17,128,960,997][i%5],actual.length-at);actual.set(pcm(b,n),at);at+=n;}
 assert.deepEqual(actual,expected);
 assert.equal(a.stats().phaseCycles720,b.stats().phaseCycles720);
 assert(expected.every(v=>Number.isFinite(v)&&Math.abs(v)<.55));
 assert(a.stats().phaseCycles720>7);
});

test('region switches with one shared 720-degree clock and bounded fade, not random reseek',()=>{
 const a=voice(),b=voice();
 for(const v of [a,b])v.setControl(960,.3);
 const all=new Float32Array(65000);
 let maxJump=0,at=0;
 for(let i=0;i<65000;i++){
  if(i===16000) {a.setControl(1500,.8);b.setControl(1500,.8);}
  if(i===45000) {a.setControl(960,.3);b.setControl(960,.3);}
  all[i]=a.next();
  assert.equal(all[i],b.next());
  if(i)maxJump=Math.max(maxJump,Math.abs(all[i]-all[i-1]));
 }
 assert.equal(a.stats().switchCount,2);
 assert.equal(a.stats().activeRegion,'low_rpm');
 assert.equal(a.stats().nonfinite,0);
 assert(maxJump<.03,'synthetic matched-phase transition generated click of '+maxJump);
 assert(a.stats().preMixPeak<.55);
});

test('missing coordinated candidate is identical to the default legacy renderer',()=>{
 const bank=fixtureBank({constant:true}),baseline=new BankRenderer(bank),other=new BankRenderer(bank);
 const x=baseline.render(state(960,.3),30000),y=new Float32Array(x.length);
 other.setState(state(960,.3));for(let i=0;i<y.length;i++)y[i]=other.next(undefined);
 assert.deepEqual(x,y);
 const original=live(null,false),unarmed=live(null,true);
 assert.deepEqual(stream(original,26000),stream(unarmed,26000));
});

test('actual live consumer selects synthetic long take with original event path and stats',()=>{
 const candidate=coordinatedSyntheticFixture(),engine=live(candidate);
 engine.command({type:'input',source:'demo',scenario:'cruise'});
 const out=stream(engine,25000);
 assert(out.some(v=>Math.abs(v)>.01));
 const snapshot=engine.snapshot();
 assert.equal(snapshot.coordinatedVoice.sourceKind,'SYNTHETIC_TEST_ONLY');
 assert.equal(snapshot.coordinatedVoice.renderedFrames,25000);
 assert(snapshot.coordinatedVoice.preMixPeak>.10);
 assert.equal(snapshot.outputAboveContractFrames,0);
 assert(out.every(x=>Number.isFinite(x)&&Math.abs(x)<=PEAK_CONTRACT));
 // Original event mixer still adds one-shot events after sustained replacement.
 const eventBank={...fixtureBank({constant:true}),vehicleKey:'hellcat_v6'};
 const r=new BankRenderer(eventBank),s={...state(),timeS:12,shiftTrigger:true,afterfireTrigger:true};
 r.setState(s);
 assert.equal(r.next(0),Math.fround(.3+Math.fround(.2)));
 r.setState(s);assert.equal(r.next(0),Math.fround(-.2+Math.fround(-.1)));
 r.setState(s);assert.equal(r.next(0),Math.fround(.1+Math.fround(.04)));
 r.setState(s);assert.equal(r.next(0),0);
});

test('opt-in rejects legacy modes, other vehicles and unverified sources without fallback',()=>{
 const c=coordinatedSyntheticFixture(),hellcat={...fixtureBank(),vehicleKey:'hellcat_v6'};
 assert.throws(()=>new LiveEngine(hellcat,'LEGACY_LOCKED',1,{recordedCandidate:c,recordedVerified:true}),/explicit Hellcat/);
 assert.throws(()=>new LiveEngine(fixtureBank(),'NORMAL_SEAM_ENVELOPE_V1',1,{recordedCandidate:c,recordedVerified:true}),/explicit Hellcat/);
 assert.throws(()=>new LiveEngine(hellcat,'NORMAL_SEAM_ENVELOPE_V1',1,{recordedCandidate:c,recordedVerified:false}),/verified/);
});

test('input owner source switch, GPS invalidation and stop cannot restart recorded loop',()=>{
 const e=live(coordinatedSyntheticFixture());
 e.command({type:'input',source:'demo',scenario:'cruise'});
 stream(e,12000);
 const was=e.snapshot().coordinatedVoice.renderedFrames;
 e.command({type:'input',source:'gps',valid:false});
 stream(e,4800);
 assert.equal(e.snapshot().coordinatedVoice.renderedFrames,was);
 assert.equal(e.snapshot().coordinatedVoice.cancelled,true);
 e.command({type:'input',source:'demo',scenario:'overspeed'});
 stream(e,4000);
 assert.equal(e.snapshot().coordinatedVoice.renderedFrames,was);
 e.command({type:'stop'});
 // Existing stop envelope updates once per 20ms; ~0.21s is insufficient.
 // Preserve original engine's fade, then require a bounded completed stop.
 for(let i=0;i<48000;i++){if(i%9600===0)e.command({type:'heartbeat'});e.next();}
 assert.equal(e.stopped,true);
 assert.equal(e.snapshot().outputNonfinite,0);
});

test('one controlled long-take trace differs from .553846s short-loop recurrence',()=>{
 const v=voice();v.setControl(960,.3);
 const n=70000, out=pcm(v,n),lag=Math.round(.553846*48000);
 let diff=0;
 for(let i=1000;i<10000;i++)diff+=Math.abs(out[i]-out[i+lag]);
 assert(diff/9000>.004,'synthetic long-form fixture unexpectedly repeats old .553846s cycle');
 // This is a synthetic recurrence counterexample, NOT evidence of real Hellcat timbre.
});
