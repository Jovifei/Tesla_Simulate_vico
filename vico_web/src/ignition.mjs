const MAX_SOURCE_FRAMES = 2 * 1024 * 1024;
const validRate = (rate, minimum) => Number.isSafeInteger(rate) && rate >= minimum && rate <= 192000;

/** PCM-only one-shot on the output audio clock. SHA verification belongs to the loader.
 * Owners are increasing positive session tokens; a cancelled token cannot resume.
 */
export class IgnitionSequence {
  #samples = null;
  #sourceRate = 0;
  #outputRate;
  #totalOutputFrames = 0;
  #outputFrames = 0;
  #owner = null;
  #lastOwner = 0;
  #stage = 'unavailable';
  #sha256;

  constructor(asset, outputRate) {
    if (!validRate(outputRate, 16000)) throw new Error('Invalid ignition output rate');
    this.#outputRate = outputRate;
    if (asset === null || asset === undefined) return;
    if (typeof asset !== 'object' || !(asset.samples instanceof Float32Array)) throw new Error('Expected mono Float32Array PCM asset');
    if (!asset.samples.length || asset.samples.length > MAX_SOURCE_FRAMES) throw new Error('Ignition PCM frame bound');
    if (!validRate(asset.sampleRate, 8000)) throw new Error('Invalid ignition source rate');
    if (asset.sha256 !== undefined && (typeof asset.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(asset.sha256))) throw new Error('Invalid ignition SHA-256 token');
    // Own the validated bytes so a caller cannot change them during playback.
    this.#samples = new Float32Array(asset.samples);
    for (let i = 0; i < this.#samples.length; i++) {
      if (!Number.isFinite(this.#samples[i])) throw new Error('Non-finite ignition PCM');
    }
    this.#sourceRate = asset.sampleRate;
    this.#sha256 = asset.sha256;
    this.#totalOutputFrames = Math.ceil(this.#samples.length * outputRate / this.#sourceRate);
    this.#stage = 'ready';
  }

  start(ownerId) {
    if (!this.#samples || !Number.isSafeInteger(ownerId) || ownerId <= this.#lastOwner) return false;
    this.cancel();
    this.#lastOwner = ownerId;
    this.#owner = ownerId;
    this.#outputFrames = 0;
    this.#stage = 'playing';
    return true;
  }

  /** null hands off to continuous sound; zero remains an ordinary PCM sample.
   * Mute terminates startup immediately. Unmute needs a fresh explicit start.
   * No allocation or wall-clock scheduling occurs on the per-frame path.
   */
  next(ownerId, muted = false) {
    if (this.#stage !== 'playing' || ownerId !== this.#owner) return null;
    if (muted) { this.cancel(ownerId); return 0; }
    const position = this.#outputFrames * this.#sourceRate / this.#outputRate;
    const last = this.#samples.length - 1;
    const left = Math.min(Math.floor(position), last);
    const right = Math.min(left + 1, last);
    const sample = Math.fround(this.#samples[left] + (this.#samples[right] - this.#samples[left]) * (position - left));
    if (++this.#outputFrames === this.#totalOutputFrames) this.#stage = 'ended';
    return sample;
  }

  cancel(ownerId) {
    if (this.#stage !== 'playing' || (ownerId !== undefined && ownerId !== this.#owner)) return false;
    this.#stage = 'cancelled';
    return true;
  }

  snapshot() {
    return {stage: this.#stage, owner: this.#owner, sourceFrames: this.#samples?.length ?? 0,
      outputFrames: this.#outputFrames, ended: this.#stage === 'ended' || this.#stage === 'cancelled' || this.#stage === 'unavailable',
      sha256: this.#sha256};
  }
}
