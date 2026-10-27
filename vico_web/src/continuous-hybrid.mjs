const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
const finite = x => typeof x === 'number' && Number.isFinite(x);
const f = Math.fround;

export class ContinuousTextureReader {
  constructor(samples, sampleRate) {
    if (!(samples instanceof Float32Array) || !Number.isSafeInteger(sampleRate) || sampleRate < 8000) throw new Error('Invalid texture');
    this.samples = samples;
    this.rate = sampleRate;
    this.phase = 0;
    this.resets = 0;
  }
  next(rpm) {
    if (!finite(rpm) || rpm < 0) throw new Error('Invalid texture RPM');
    const n = this.samples.length;
    const p = ((this.phase % n) + n) % n;
    const i = Math.floor(p);
    const j = (i + 1) % n;
    const value = f(this.samples[i] + (this.samples[j] - this.samples[i]) * (p - i));
    this.phase += Math.max(0.05, rpm / 120 / this.rate);
    return value;
  }
}

export function makeRaisedCosineEvent(samples, durationFrames) {
  if (!(samples instanceof Float32Array) || !Number.isSafeInteger(durationFrames) || durationFrames < samples.length * 2) throw new Error('Invalid event');
  return {samples, durationFrames};
}

export class ContinuousHybridRenderer {
  constructor({sampleRate, texture, textureWeight = .35, base = () => 0, envelopeTimeS = .08} = {}) {
    if (!Number.isSafeInteger(sampleRate) || sampleRate < 8000) throw new Error('Invalid hybrid sample rate');
    this.rate = sampleRate;
    this.reader = texture instanceof Float32Array ? new ContinuousTextureReader(texture, sampleRate) : null;
    this.textureWeight = this.reader ? clamp(textureWeight, 0, .8) : 0;
    this.base = base;
    this.alpha = 1 - Math.exp(-1 / Math.max(1, sampleRate * envelopeTimeS));
    this.envelope = 0;
    this.envelopeMin = 1;
    this.envelopeMax = 0;
    this.event = null;
    this.eventAt = 0;
  }
  trigger(event) {
    if (!event || !(event.samples instanceof Float32Array) || !Number.isSafeInteger(event.durationFrames)) throw new Error('Invalid hybrid event');
    this.event = event;
    this.eventAt = 0;
  }
  next({rpm, load = 0, accel = 0} = {}) {
    if (!finite(rpm) || !finite(load) || !finite(accel)) throw new Error('Invalid hybrid state');
    const target = clamp(.16 + .55 * clamp(load, 0, 1) + .16 * clamp(Math.abs(accel) / 3, 0, 1), .08, .92);
    this.envelope += this.alpha * (target - this.envelope);
    this.envelopeMin = Math.min(this.envelopeMin, this.envelope);
    this.envelopeMax = Math.max(this.envelopeMax, this.envelope);
    const base = f(this.base({rpm, load, accel}) * this.envelope);
    const texture = this.reader ? f(this.reader.next(rpm) * this.textureWeight * this.envelope) : 0;
    let event = 0;
    if (this.event && this.eventAt < this.event.durationFrames) {
      const n = this.event.durationFrames;
      const p = this.eventAt / Math.max(1, n - 1);
      const source = this.event.samples[Math.min(this.event.samples.length - 1, Math.floor(p * this.event.samples.length))];
      const attack = Math.min(1, this.eventAt / Math.max(1, this.event.samples.length));
      const release = clamp((n - 1 - this.eventAt) / Math.max(1, this.event.samples.length), 0, 1);
      event = f(source * (.5 - .5 * Math.cos(Math.PI * attack)) * (.5 - .5 * Math.cos(Math.PI * release)));
      this.eventAt++;
    } else if (this.event) {
      this.event = null;
    }
    return clamp(f(base + texture + event), -1, 1);
  }
}
