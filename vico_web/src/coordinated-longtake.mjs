/**
 * HC-C1 coordinated long-take source. Original DSP, not a claim of Hellcat
 * calibration. One prevalidated mono take, disjoint synchronized 720-degree
 * spans and ONE shared crank-phase readhead; never load/network/allocate in next().
 */
export const LONG_TAKE_SCHEMA = 'vico.coordinated.longtake.v1';
export const LONG_TAKE_MAX_SECONDS = 60;
const MAX_REGIONS = 8;
const TRANSITION_SECONDS = .120;
const DWELL_SECONDS = .250;
const BOUNDARY_LIMIT = .12;
const isSha = s => typeof s === 'string' && /^[0-9a-f]{64}$/.test(s);
const finite = x => typeof x === 'number' && Number.isFinite(x);
const clamp = (v,lo,hi)=>Math.max(lo,Math.min(hi,v));

/** Caller is responsible for upstream source-license evidence, not an AI tool. */
export function validateLongTake(candidate) {
  if (!candidate || candidate.schema!==LONG_TAKE_SCHEMA ||
      candidate.vehicleKey!=='hellcat_v6' || candidate.sampleRate!==48000 ||
      !(candidate.samples instanceof Float32Array) ||
      candidate.samples.length<96000 || candidate.samples.length>48000*LONG_TAKE_MAX_SECONDS ||
      !isSha(candidate.pcmSha256) || typeof candidate.takeId!=='string' ||
      !/^[a-zA-Z0-9_.-]{8,80}$/.test(candidate.takeId))
    throw new Error('Invalid coordinated-take source identity');
  const e=candidate.evidence;
  const synthetic=e?.sourceClass==='SYNTHETIC_TEST_ONLY' && e.licenseGate==='NOT_DISTRIBUTABLE_TEST' &&
    e.captureState==='SYNTHETIC_KNOWN_RPM_LOAD' && e.phaseState==='SYNTHETIC_KNOWN_720';
  const approved=e?.sourceClass==='LICENSED_RECORDED_TAKE' && e.licenseGate==='PRODUCT_DISTRIBUTION_CLEARED' &&
    e.captureState==='SYNCHRONIZED_MEASURED_RPM_LOAD' && e.phaseState==='VERIFIED_720_PHASE' &&
    e.holdoutState==='INDEPENDENT_LOCKED' && typeof e.approvalId==='string' &&
    /^[a-zA-Z0-9_.-]{12,96}$/.test(e.approvalId);
  if(!synthetic&&!approved)throw new Error('Recorded take lacks explicit license/state/phase/holdout qualifications');
  if(!Array.isArray(candidate.regions) || candidate.regions.length<2 || candidate.regions.length>MAX_REGIONS)
    throw new Error('Coordinated take requires multiple regions from one source');
  let end=0;
  const ids=new Set();
  for(const r of candidate.regions){
    if(!r || typeof r.id!=='string' || !/^[a-z0-9_-]{3,32}$/.test(r.id) || ids.has(r.id) ||
       !Number.isSafeInteger(r.startFrame)||!Number.isSafeInteger(r.endFrame) ||
       r.startFrame<end || r.endFrame>candidate.samples.length ||
       r.endFrame-r.startFrame<48000 || r.endFrame-r.startFrame>48000*12 ||
       !Number.isSafeInteger(r.cycles720)||r.cycles720<4||r.cycles720>300 ||
       !finite(r.referenceRpm)||r.referenceRpm<500||r.referenceRpm>10000 ||
       !finite(r.referenceLoad)||r.referenceLoad<0||r.referenceLoad>1)
      throw new Error('Invalid/disconnected coordinated source region');
    ids.add(r.id);
    const n=r.endFrame-r.startFrame;
    // Only an independently marked phase-complete region can traverse a lap.
    const inferred=r.cycles720*120*48000/n;
    if(Math.abs(inferred-r.referenceRpm)>r.referenceRpm*.015)
      throw new Error('Region cycle count inconsistent with synchronized reference RPM');
    if(Math.abs(candidate.samples[r.startFrame]-candidate.samples[r.endFrame-1])>BOUNDARY_LIMIT)
      throw new Error('Unaligned region boundary');
    end=r.endFrame;
  }
  for(const x of candidate.samples){
    if(!finite(x)||Math.abs(x)>.55)throw new Error('Nonfinite/excessive source PCM');
  }
  return Object.freeze({
    vehicleKey:candidate.vehicleKey,sourceKind:e.sourceClass,regionCount:candidate.regions.length,
    sampleRate:candidate.sampleRate,pcmSha256:candidate.pcmSha256,qualification:'ENGINEERING_ONLY_NOT_OEM'
  });
}

export class CoordinatedLongTakeVoice {
  constructor(candidate,{alreadyVerified=false}={}){
    this.identity=validateLongTake(candidate);
    // SHA must also be checked on the main thread BEFORE transferring PCM to
    // AudioWorklet. Live Worklet only accepts a main-thread verified candidate.
    if(alreadyVerified!==true)throw new Error('Long-take F32LE SHA must be verified before audio thread');
    this.samples=candidate.samples;
    this.regions=candidate.regions.map(r=>({...r,span:r.endFrame-r.startFrame,unit:r.cycles720}));
    this.rate=48000;this.crossfadeFrames=Math.round(TRANSITION_SECONDS*this.rate);
    this.dwellFrames=Math.round(DWELL_SECONDS*this.rate);
    this.reset();
  }
  reset(){
    this.cycles=0;this.active=-1;this.target=-1;this.transition=0;
    this.dwell=this.dwellFrames;this.rendered=0;this.rpm=1000;this.load=0;this.cancelled=false;
    this.peak=0;this.nonfinite=0;this.switches=0;this.laps=0;this.lastCycle=0;
  }
  /** Control is updated on the PCM clock, never on wall-clock animation frames. */
  setControl(rpm,load){
    if(!finite(rpm)||!finite(load)||rpm<0||load<0||load>1)throw new Error('Invalid long-take state');
    if(this.cancelled)return;
    this.rpm=clamp(rpm,500,10000);this.load=load;
    const score=r=>Math.pow(Math.log(this.rpm/r.referenceRpm)/.35,2)+Math.pow((load-r.referenceLoad)/.3,2);
    let best=0;
    for(let i=1;i<this.regions.length;i++)if(score(this.regions[i])<score(this.regions[best]))best=i;
    if(this.active===-1){this.active=best;return;}
    if(this.target!==-1||this.dwell<this.dwellFrames)return;
    if(best!==this.active && score(this.regions[best])+.15<score(this.regions[this.active])){
      this.target=best;this.transition=0;this.switches++;
    }
  }
  read(index){
    const r=this.regions[index];
    const phase=((this.cycles%r.unit)+r.unit)%r.unit;
    const x=phase/r.unit*r.span;
    const i=Math.floor(x),j=i+1>=r.span?0:i+1;
    const a=this.samples[r.startFrame+i],b=this.samples[r.startFrame+j];
    return Math.fround(a+(b-a)*(x-i));
  }
  next(){
    if(this.cancelled)return 0;
    if(this.active<0)throw new Error('Long-take control not initialized');
    let v=this.read(this.active);
    if(this.target>=0){
      const t=this.transition/this.crossfadeFrames;
      const smooth=t*t*(3-2*t);
      v=Math.fround(v*(1-smooth)+this.read(this.target)*smooth);
      if(++this.transition>=this.crossfadeFrames){
        this.active=this.target;this.target=-1;this.transition=0;this.dwell=0;
      }
    }
    const increment=this.rpm/(120*this.rate);
    this.cycles+=increment;
    if(Math.floor(this.cycles)>Math.floor(this.lastCycle))this.laps++;
    this.lastCycle=this.cycles;
    this.rendered++;this.dwell++;
    if(!Number.isFinite(v)){this.nonfinite++;throw new Error('Nonfinite long-take sample');}
    this.peak=Math.max(this.peak,Math.abs(v));
    return v;
  }
  cancel(){this.cancelled=true;this.target=-1;}
  stats(){return {schema:'vico.longtake.snapshot.v1',sourceKind:this.identity.sourceKind,
    qualification:'SYNTHETIC_OR_LICENSE_GATED_NOT_ACOUSTIC_APPROVAL',sourceSHA256:this.identity.pcmSha256,
    regions:this.identity.regionCount,activeRegion:this.active<0?null:this.regions[this.active].id,
    transitioning:this.target>=0,renderedFrames:this.rendered,preMixPeak:this.peak,
    nonfinite:this.nonfinite,switchCount:this.switches,phaseCycles720:this.cycles,cancelled:this.cancelled};}
}
