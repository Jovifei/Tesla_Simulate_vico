import {IgnitionSequence} from './ignition.mjs';
import {CoordinatedLongTakeVoice} from './coordinated-longtake.mjs';

/** Vico Kotlin algorithm port. Original assets/gains remain authoritative.
 * Based on PR38 477913e7: NOT an OEM model or a new acoustic qualification.
 */
export const SOURCE_SHA = '477913e7500bb3ff13c3b72cf5b1a3cac1b28145';
export const MODES = Object.freeze(['LEGACY_LOCKED', 'NORMAL_CANONICAL_SEAM_V1', 'NORMAL_SEAM_ENVELOPE_V1']);
export const PEAK_CONTRACT = 0.8413951416451951;
const f = Math.fround;
export const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
const lerp = (a, b, t) => f(a + f(f(b - a) * f(t)));
const finite = (x, label) => { if (!Number.isFinite(x)) throw new Error(`Non-finite ${label}`); return x; };

export function decodeF32Wav(buffer) {
  const v = buffer instanceof DataView ? buffer : new DataView(buffer);
  const text = (p, n) => String.fromCharCode(...new Uint8Array(v.buffer, v.byteOffset + p, n));
  if (v.byteLength < 44 || v.byteLength > 8 * 1024 * 1024 || text(0, 4) !== 'RIFF' || text(8, 4) !== 'WAVE') throw new Error('Invalid WAV container');
  const end = v.getUint32(4, true) + 8;
  if (end !== v.byteLength) throw new Error('WAV length mismatch');
  let fmt = null, data = null;
  for (let p = 12; p + 8 <= end;) {
    const n = v.getUint32(p + 4, true), at = p + 8, tag = text(p, 4);
    if (at + n > end) throw new Error('Truncated WAV chunk');
    if (tag === 'fmt ') {
      if (fmt || n < 16) throw new Error('Invalid WAV format');
      let code = v.getUint16(at, true);
      if (code === 65534 && n >= 40) code = v.getUint16(at + 24, true);
      fmt = {code, channels: v.getUint16(at + 2, true), sampleRate: v.getUint32(at + 4, true), bits: v.getUint16(at + 14, true), align: v.getUint16(at + 12, true)};
    } else if (tag === 'data') {
      if (data) throw new Error('Multiple PCM chunks');
      data = {at, n};
    }
    p = at + n + (n & 1);
  }
  if (!fmt || !data || fmt.code !== 3 || fmt.channels !== 1 || fmt.bits !== 32 || fmt.align !== 4 || ![48000, 96000].includes(fmt.sampleRate) || !data.n || data.n % 4) throw new Error('Expected mono F32LE 48/96k WAV');
  const samples = new Float32Array(data.n / 4);
  for (let i = 0; i < samples.length; i++) samples[i] = finite(v.getFloat32(data.at + i * 4, true), 'PCM');
  return {samples, sampleRate: fmt.sampleRate};
}

export function validateSpec(s) {
  for (const k of ['idle_rpm','redline_rpm','final_drive','wheel_radius_m','launch_rpm','shift_rpm','shift_attack_s','shift_hold_s','shift_recovery_s','shift_settle_s','shift_min_torque','shift_reengage_gain','minimum_shift_interval_s','downshift_ratio','speed_ceiling_kmh','afterfire_minimum_rpm']) finite(s[k], k);
  if (!(s.idle_rpm > 0 && s.redline_rpm >= s.idle_rpm && s.final_drive > 0 && s.wheel_radius_m > 0 && s.speed_ceiling_kmh > 0) || !Array.isArray(s.gear_ratios) || !s.gear_ratios.length || s.gear_ratios.some(x => !Number.isFinite(x) || x <= 0)) throw new Error('Invalid powertrain spec');
  for (const k of ['shift_attack_s','shift_hold_s','shift_recovery_s','shift_settle_s','minimum_shift_interval_s']) if (s[k] < 0) throw new Error(`Negative ${k}`);
  return s;
}

class Envelope {
  constructor(rate) { this.a = 1 - Math.exp(-1 / (rate * .050)); this.b = 1 - Math.exp(-1 / (rate * .600)); this.c = 1 - Math.exp(-1 / (rate * .005)); this.warmup = rate / 4; this.reset(); }
  reset() { this.frames = 0; this.fast = 0; this.slow = 0; this.gain = 1; this.min = 1; this.max = 1; }
  process(sample) {
    const energy = sample * sample;
    this.fast += this.a * (energy - this.fast); this.slow += this.b * (energy - this.slow);
    if (++this.frames <= this.warmup) return sample;
    const target = Math.max(this.fast, this.slow) < 1e-10 ? 1 : clamp(1 + .3 * (Math.sqrt((this.slow + 1e-12) / (this.fast + 1e-12)) - 1), .97, 1.03);
    this.gain += this.c * (target - this.gain); this.min = Math.min(this.min, this.gain); this.max = Math.max(this.max, this.gain);
    return f(sample * this.gain);
  }
}

export class BankRenderer {
  constructor(bank, mode = 'NORMAL_SEAM_ENVELOPE_V1') {
    if (!MODES.includes(mode) || ![48000, 96000].includes(bank.sampleRate) || !bank.loops?.length || bank.loops.length > 64) throw new Error('Invalid renderer configuration');
    this.bank = bank; this.mode = mode; this.rate = bank.sampleRate;
    this.rpms = [...new Set(bank.loops.map(l => l.rpm))].sort((a,b) => a-b);
    this.loads = [...new Set(bank.loops.map(l => l.load))].sort((a,b) => a-b);
    if (this.rpms.some(x => !Number.isFinite(x) || x <= 0) || this.loads.some(x => !Number.isFinite(x))) throw new Error('Invalid bank axes');
    this.grid = this.rpms.flatMap(rpm => this.loads.map(load => {
      const matches = bank.loops.filter(l => l.rpm === rpm && l.load === load);
      if (matches.length !== 1) throw new Error('Incomplete or duplicate loop grid');
      const l = matches[0], x = l.samples;
      if (!(x instanceof Float32Array) || !x.length || x.length > 1440000 || x.some(v => !Number.isFinite(v))) throw new Error('Invalid loop PCM');
      const wrap = x[0] - x[x.length-1];
      return {samples: x, span: x.length / this.rate * rpm / 120, eligible: x.length >= 85, d1: wrap - (x[x.length-1] - x[x.length-2]), d2: x[1] - x[0] - wrap};
    }));
    for (const pcm of [bank.afterfire, ...(bank.shifts || [])]) if (!(pcm instanceof Float32Array) || pcm.some(v => !Number.isFinite(v))) throw new Error('Invalid event PCM');
    this.alpha = 1 - Math.exp(-1 / (this.rate * .035)); this.envelope = new Envelope(this.rate); this.reset();
  }
  reset() { this.cycles = 0; this.rpm = NaN; this.load = NaN; this.frames = 0; this.peak = 0; this.excess = 0; this.hardClips = 0; this.nonfinite = 0; this.corrections = 0; this.shiftNumber = 0; this.state = null; this.envelope.reset(); this.clearEvents(); }
  clearEvents() { this.afterAt = -1; this.shiftAt = -1; this.shift = null; this.lastAfter = NaN; this.lastShift = NaN; }
  setState(s) {
    for (const k of ['timeS','rpm','load','shiftGain']) finite(s[k], k);
    this.state = s;
    if (s.muted) return;
    if (s.afterfireTrigger && s.timeS !== this.lastAfter) { this.lastAfter = s.timeS; this.afterAt = 0; }
    if (s.shiftTrigger && s.timeS !== this.lastShift) { this.lastShift = s.timeS; this.shift = this.bank.shifts.length ? this.bank.shifts[this.shiftNumber++ % this.bank.shifts.length] : null; this.shiftAt = this.shift ? 0 : -1; }
  }
  bound(levels, x) { let i = 0; while (i + 1 < levels.length && levels[i+1] <= x) i++; return i; }
  sample(l) {
    const x = l.samples, n = x.length, p = (this.cycles % l.span) / l.span * n, i = Math.floor(p) % n;
    const legacy = lerp(x[i], x[(i+1)%n], f(p - Math.floor(p)));
    if (this.mode === 'LEGACY_LOCKED' || !l.eligible || p >= 8 && p <= n-9) return legacy;
    const u0 = p > n/2 ? p-n : p;
    let u1 = p-(n-1); if (u1 < -n/2) u1 += n;
    const correction = this.soften(u1,l.d1) + this.soften(u0,l.d2);
    if (correction === 0) return legacy;
    this.corrections++; return f(legacy + correction);
  }
  soften(distance, delta) { const u = Math.abs(distance); return u >= 8 ? 0 : -delta / 2 * u * (1 + Math.cos(Math.PI * u / 8)) / 2; }
  next(continuousOverride=undefined) {
    const s = this.state; if (!s) throw new Error('Missing renderer state');
    if (s.muted) { this.frames++; return 0; }
    const r = clamp(s.rpm,this.rpms[0],this.rpms.at(-1)), l = clamp(s.load,this.loads[0],this.loads.at(-1));
    if (!Number.isFinite(this.rpm)) this.rpm = r; if (!Number.isFinite(this.load)) this.load = l;
    this.rpm += this.alpha * (r-this.rpm); this.load += this.alpha * (l-this.load);
    const ri = this.bound(this.rpms,this.rpm), li = this.bound(this.loads,this.load);
    const rj = this.rpm === this.rpms[ri] ? ri : Math.min(ri+1,this.rpms.length-1), lj = this.load === this.loads[li] ? li : Math.min(li+1,this.loads.length-1);
    const rw = ri === rj ? 0 : f((this.rpm-this.rpms[ri])/(this.rpms[rj]-this.rpms[ri])), lw = li === lj ? 0 : f((this.load-this.loads[li])/(this.loads[lj]-this.loads[li]));
    const width = this.loads.length;
    const low = lerp(this.sample(this.grid[ri*width+li]),this.sample(this.grid[ri*width+lj]),lw);
    const high = lerp(this.sample(this.grid[rj*width+li]),this.sample(this.grid[rj*width+lj]),lw);
    // HC-C1 replaces ONLY sustained dry sound. Original time, shift, afterfire,
    // output peak counters and sample-clock progression are still authoritative.
    let dry = lerp(low,high,rw);
    if (continuousOverride !== undefined) {
      dry = f(finite(continuousOverride,'recorded continuous sample'));
    } else if (this.mode === 'NORMAL_SEAM_ENVELOPE_V1') dry = this.envelope.process(dry);
    let value = f(dry * f(s.shiftGain));
    if (this.afterAt >= 0 && this.afterAt < this.bank.afterfire.length) value = f(value + this.bank.afterfire[this.afterAt++]);
    if (this.shift && this.shiftAt >= 0 && this.shiftAt < this.shift.length) { value = f(value + this.shift[this.shiftAt++]); if (this.shiftAt === this.shift.length) { this.shift = null; this.shiftAt = -1; } }
    this.frames++;
    if (!Number.isFinite(value)) { this.nonfinite++; throw new Error('Non-finite mix'); }
    this.peak = Math.max(this.peak,Math.abs(value)); if (Math.abs(value)>PEAK_CONTRACT) this.excess++; if (Math.abs(value)>1) this.hardClips++;
    this.cycles += this.rpm / 120 / this.rate;
    return clamp(value,-1,1);
  }
  render(state, frames) { if (!Number.isSafeInteger(frames) || frames < 0 || frames > 1440000) throw new Error('Capture bound'); this.setState(state); const out = new Float32Array(frames); for (let i=0;i<frames;i++) out[i]=this.next(); return out; }
  stats() { return {frames:this.frames,preClipPeak:this.peak,aboveContract:this.excess,hardClips:this.hardClips,nonfinite:this.nonfinite,correctedReads:this.corrections,envelopeMin:this.envelope.min,envelopeMax:this.envelope.max,algorithm:this.mode}; }
}

export class DemoMotion {
  constructor(speed = 0) { this.speed = speed; this.accel = 0; }
  step(dt, scenario, manualTarget = 0) {
    dt = clamp(finite(dt,'dt'),.001,.1);
    const target = ({launch:60,cruise:80,overspeed:144,decel:0,stop:0,manual:clamp(manualTarget,0,144)})[scenario];
    if (target === undefined) throw new Error('Unknown scenario');
    const forward = scenario === 'launch' ? 3.5 : scenario === 'overspeed' ? 2.5 : 2;
    const brake = scenario === 'decel' ? 4 : 3.2;
    let demand = clamp((target-this.speed)*.52,-brake,forward); if (Math.abs(target-this.speed)<.18) demand=0;
    this.accel += clamp(demand-this.accel,-5.5*dt,5.5*dt); this.speed = Math.max(0,this.speed+this.accel*dt*3.6);
    if (target===0 && this.speed<.2 && Math.abs(this.accel)<.1 || target>0 && Math.abs(this.speed-target)<.08 && Math.abs(this.accel)<.05) { this.speed=target; this.accel=0; }
  }
}

export class Powertrain {
  constructor(spec) { this.s=validateSpec(spec); this.up=spec.gear_ratios.slice(0,-1).map(r=>spec.shift_rpm/60/(r*spec.final_drive)*(2*Math.PI*spec.wheel_radius_m)*3.6); this.reset(); }
  reset() { this.gear=1; this.rpm=this.s.idle_rpm; this.lastTime=NaN; this.lastShift=-Infinity; this.shiftStart=-Infinity; this.lastThrottle=0; this.armed=false; }
  update(timeS,speed,accel,throttle) {
    [timeS,speed,accel,throttle].forEach(v=>finite(v,'control')); const s=this.s;
    speed=clamp(speed,0,s.speed_ceiling_kmh); throttle=clamp(throttle,0,1);
    const dt=Number.isFinite(this.lastTime)?clamp(timeS-this.lastTime,.001,.2):.05; this.lastTime=timeS;
    let shifted=false;
    if (timeS-this.lastShift>=s.minimum_shift_interval_s) {
      if (accel>.15 && this.gear<s.gear_ratios.length && speed>=this.up[this.gear-1]) { this.gear++; shifted=true; }
      else if (accel<-.15 && this.gear>1 && speed<=s.downshift_ratio*this.up[this.gear-2]) { this.gear--; shifted=true; }
    }
    if (shifted) { this.lastShift=timeS; this.shiftStart=timeS; }
    const t=timeS-this.shiftStart, total=s.shift_attack_s+s.shift_hold_s+s.shift_recovery_s+s.shift_settle_s;
    let gain=1,coupling=1,p;
    const blend=(a,b,u)=>a+(b-a)*(.5-.5*Math.cos(Math.PI*clamp(u,0,1)));
    if (t>=0 && t<s.shift_attack_s) { p=t/s.shift_attack_s; gain=blend(1,s.shift_min_torque,p); coupling=.08+.18*p; }
    else if (t>=0 && t<s.shift_attack_s+s.shift_hold_s) { gain=s.shift_min_torque; coupling=.22; }
    else if (t>=0 && t<s.shift_attack_s+s.shift_hold_s+s.shift_recovery_s) { p=(t-s.shift_attack_s-s.shift_hold_s)/s.shift_recovery_s; gain=blend(s.shift_min_torque,s.shift_reengage_gain,p); coupling=.24+.56*p; }
    else if (t>=0 && t<total) { p=(t-s.shift_attack_s-s.shift_hold_s-s.shift_recovery_s)/s.shift_settle_s; gain=blend(s.shift_reengage_gain,1,p); coupling=.8+.2*p; }
    const mps=speed/3.6, target=Math.max(s.idle_rpm,mps/(2*Math.PI*s.wheel_radius_m)*60*s.final_drive*s.gear_ratios[this.gear-1]);
    this.rpm=t>=0&&t<=total?this.rpm+(1-Math.pow(1-coupling,Math.max(1,dt*1000)))*(target-this.rpm):target;
    this.rpm=Math.min(s.redline_rpm,Math.max(this.rpm,s.idle_rpm+throttle*(s.launch_rpm-s.idle_rpm)*(1-Math.min(1,mps/4))));
    if (this.rpm>=s.afterfire_minimum_rpm&&throttle>=.25) this.armed=true;
    const after=this.rpm>=s.afterfire_minimum_rpm&&(shifted||this.lastThrottle-throttle>.24||accel<-1.2&&this.armed);
    if (after) this.armed=false; this.lastThrottle=throttle;
    return {timeS,rpm:this.rpm,load:clamp(throttle*gain,0,1),shiftGain:gain,gear:this.gear,shiftTrigger:shifted,afterfireTrigger:after,muted:speed>=148};
  }
}

/** Browser GPS is deliberately not Android REAL/IMU equivalence. Coordinates never retained. */
export class GpsSpeedInput {
  constructor() { this.lastTime=0; this.lastSpeed=0; }
  accept(position, now=Date.now()) {
    const speed=position?.coords?.speed, timestamp=position?.timestamp;
    if (!Number.isFinite(speed)||speed<0||speed>100||!Number.isFinite(timestamp)||timestamp<=this.lastTime||now-timestamp>2000||timestamp>now+250) return {valid:false};
    const dt=(timestamp-this.lastTime)/1000, kmh=speed*3.6;
    const accel=this.lastTime&&dt>0&&dt<=3?clamp((speed-this.lastSpeed)/dt,-4,3.5):0;
    this.lastTime=timestamp; this.lastSpeed=speed;
    return {valid:true,speedKmh:kmh,accelMps2:accel,ageMs:Math.max(0,now-timestamp),source:'WEB_GPS_ESTIMATED'};
  }
}

/** Sample-clocked normal playback. No wall-clock prediction and no future REAL plan. */
export class LiveEngine {
  constructor(bank, mode, ownerId=1, {recordedCandidate=null, recordedVerified=false}={}) {
    if(!Number.isSafeInteger(ownerId)||ownerId<=0)throw new Error('Invalid playback owner');
    // This gate is never enabled from the released UI. Caller must first prove
    // F32LE SHA on the main thread; missing evidence rejects, not legacy fallback.
    if(recordedCandidate && (mode!=='NORMAL_SEAM_ENVELOPE_V1'||bank.vehicleKey!=='hellcat_v6'))
      throw new Error('Coordinated voice only permits explicit Hellcat normal mode');
    this.recorded=recordedCandidate?new CoordinatedLongTakeVoice(recordedCandidate,{alreadyVerified:recordedVerified}):null;
    this.renderer=new BankRenderer(bank,mode); this.power=new Powertrain(bank.spec); this.motion=new DemoMotion(); this.rate=bank.sampleRate; this.controlFrames=this.rate/50;
    const start=mode==='NORMAL_SEAM_ENVELOPE_V1'?bank.startup:null;
    this.ownerId=ownerId;this.ignition=new IgnitionSequence(start,this.rate);this.starting=this.ignition.start(ownerId);this.startupFrame=0;
    this.outputPeak=0;this.outputExcess=0;this.outputNonfinite=0;
    this.startupTotal=start?.samples.length||0;this.startupFade=Math.max(1,Math.round(this.rate*(start?.fadeInMs??5)/1000));this.startupHandoff=Math.max(1,Math.round(this.rate*(start?.handoffMs??150)/1000));
    this.frame=0; this.running=true; this.runGain=0; this.contentGain=0; this.source='demo'; this.scenario='stop'; this.target=0;
    this.heartbeatFrame=0; this.gpsUntil=-1; this.gpsSpeed=0; this.gpsAccel=0; this.speed=0; this.state=null; this.usable=false; this.wasUsable=false;
  }
  command(m) {
    if (m.type==='heartbeat') this.heartbeatFrame=this.frame;
    else if (m.type==='stop') {this.running=false;this.cancelStartup();if(this.recorded)this.renderer.clearEvents();}
    else if (m.type==='input') {
      if (!['demo','manual','gps'].includes(m.source)) throw new Error('Invalid source');
      if (this.source!==m.source) { this.renderer.clearEvents(); this.power.reset(); this.gpsUntil=-1; this.recorded?.cancel(); }
      this.source=m.source;
      if(m.source==='gps'||m.source==='manual'&&m.speedKmh>0)this.cancelStartup();
      if (m.source==='demo') { if (!['launch','cruise','overspeed','decel','stop'].includes(m.scenario)) throw new Error('Invalid scenario'); this.scenario=m.scenario; }
      if (m.source==='manual') this.target=clamp(finite(m.speedKmh,'target speed'),0,144);
      if (m.source==='gps') {
        if (m.valid===true && Number.isFinite(m.speedKmh) && m.speedKmh>=0 && m.speedKmh<=360 && Number.isFinite(m.accelMps2) && Number.isFinite(m.ageMs) && m.ageMs>=0 && m.ageMs<2000) {
          this.gpsSpeed=m.speedKmh; this.gpsAccel=clamp(m.accelMps2,-4,3.5); this.gpsUntil=this.frame+Math.floor((2000-m.ageMs)*this.rate/1000);
        } else this.gpsUntil=-1;
      }
    }
  }
  tick() {
    this.usable=this.running && this.frame-this.heartbeatFrame<=this.rate*.75 && (this.source!=='gps'||this.frame<this.gpsUntil);
    if(!this.usable)this.cancelStartup();
    if(this.starting){this.speed=0;this.motion.speed=0;this.motion.accel=0;}
    else if (this.source!=='gps') { this.motion.step(.02,this.source==='manual'?'manual':this.scenario,this.target); this.speed=this.motion.speed; }
    else this.speed=this.gpsSpeed;
    const accel=this.source==='gps'?this.gpsAccel:this.motion.accel;
    this.state=this.power.update(this.frame/this.rate,this.speed,accel,clamp(accel/3,0,1));
    if (this.source==='gps'||!this.usable||!this.wasUsable) { this.state.shiftTrigger=false; this.state.afterfireTrigger=false; }
    if (this.wasUsable&&!this.usable) this.renderer.clearEvents(); this.wasUsable=this.usable;
    this.state.muted=false;
    this.runGain=f(this.runGain+f(f((this.running?1:0)-this.runGain)*f(.3)));
    this.contentGain=f(this.contentGain+f(f((this.usable&&this.speed<148?1:0)-this.contentGain)*f(.3)));
    if (!this.running&&this.runGain<.001) this.runGain=0;
    if (!this.usable&&this.contentGain<.001) this.contentGain=0;
    this.renderer.setState(this.state);
    if(this.recorded && this.usable && this.source==='demo')
      this.recorded.setControl(this.state.rpm,this.state.load);
  }
  cancelStartup(){this.ignition.cancel(this.ownerId);this.starting=false;}
  next() {
    if (this.frame%this.controlFrames===0) this.tick();
    // Invalid/GPS inputs cannot activate an experimental recorded segment.
    // Content gain and existing owner's stop fade remain in charge.
    let override;
    if(this.recorded){
      // Never fall back to an unqualified synthetic bank when a prepared
      // recorded-source owner becomes invalid/cancelled in this session.
      override = this.recorded.cancelled || this.source!=='demo' ? 0
        : this.recorded.active>=0 ? this.recorded.next() : 0;
    }
    let sample=this.renderer.next(override);
    if(this.starting){
      const start=this.ignition.next(this.ownerId);
      if(start===null)this.starting=false;
      else{
        const weight=Math.min(1,(this.startupTotal-this.startupFrame)/this.startupHandoff);
        const fade=Math.min(1,(this.startupFrame+1)/this.startupFade);
        sample=f(start*fade*weight+sample*(1-weight));
        if(++this.startupFrame>=this.startupTotal)this.starting=false;
      }
    }
    this.frame++;
    const output=f(sample*f(this.runGain*this.contentGain));
    if(!Number.isFinite(output)){this.outputNonfinite++;throw new Error('Non-finite live output');}
    this.outputPeak=Math.max(this.outputPeak,Math.abs(output));if(Math.abs(output)>PEAK_CONTRACT)this.outputExcess++;
    return output;
  }
  get stopped() { return !this.running && this.runGain===0; }
  snapshot() { return {...this.renderer.stats(),...(this.recorded?{coordinatedVoice:this.recorded.stats()}:{}),speedKmh:this.speed,rpm:this.state?.rpm||0,gear:this.state?.gear||1,load:this.state?.load||0,source:this.source==='gps'?'WEB_GPS_ESTIMATED':this.source.toUpperCase(),inputUsable:this.usable,modelTimeS:this.frame/this.rate,sourceSampleRate:this.rate,startup:this.ignition.snapshot(),outputPreClipPeak:this.outputPeak,outputAboveContractFrames:this.outputExcess,outputNonfinite:this.outputNonfinite,outputDomain:'LIVE_START_AND_CONTINUOUS_POST_GATE_PRE_RESAMPLER_PRE_MASTER'}; }
}

export class StreamingResampler {
  constructor(engine, outputRate) { if (!Number.isFinite(outputRate)||outputRate<16000||outputRate>192000) throw new Error('Unsupported output rate'); this.engine=engine; this.ratio=engine.rate/outputRate; this.phase=0; this.started=false; }
  next() { if (this.ratio===1) return this.engine.next(); if (!this.started) { this.a=this.engine.next(); this.b=this.engine.next(); this.started=true; } const y=lerp(this.a,this.b,this.phase); this.phase+=this.ratio; while(this.phase>=1) { this.phase-=1; this.a=this.b; this.b=this.engine.next(); } return y; }
}
