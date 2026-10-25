export const RECORDED_REFERENCE_SCHEMA = 'vico.recorded.reference.v1';
const LICENSES = new Map([
  ['CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/'],
  ['CC0', 'https://creativecommons.org/publicdomain/zero/1.0/']
]);

const safeId = value => typeof value === 'string' && /^[a-z0-9][a-z0-9-]{2,63}$/.test(value);
const safeFile = value => typeof value === 'string' && /^[a-z0-9][a-z0-9.-]+\.wav$/.test(value) && !value.includes('..');
const safePath = value => typeof value === 'string' && /^[a-z0-9][a-z0-9/.-]+\.wav$/.test(value) && !value.includes('..');

export function validateRecordedReference(reference) {
  if (!reference || reference.schema !== RECORDED_REFERENCE_SCHEMA || reference.scope !== 'REFERENCE_ONLY')
    throw new Error('Expected a REFERENCE_ONLY recorded reference');
  if (!safeId(reference.id) || !safePath(reference.file))
    throw new Error('Invalid recorded reference id or file');
  if (!Number.isSafeInteger(reference.sampleRate) || ![24000, 48000].includes(reference.sampleRate))
    throw new Error('Unsupported reference sample rate');
  if (![1, 2].includes(reference.channels) || !Number.isSafeInteger(reference.frames) || reference.frames < 1)
    throw new Error('Invalid reference format');
  if (reference.automaticLoop !== false)
    throw new Error('Recorded references must not auto-loop');

  const source = reference.source || {};
  if (!source.author?.trim() || !LICENSES.get(source.license) || source.licenseUrl !== LICENSES.get(source.license))
    throw new Error('Missing source author/license evidence');

  const identity = reference.identity || {};
  if (!identity.vehicle?.trim() || identity.state !== 'UNKNOWN' ||
      identity.synchronizedRpmLoad !== false || identity.OEMQualification !== false)
    throw new Error('Reference claims unverified vehicle state or qualification');

  return Object.freeze({scope: reference.scope, id: reference.id, file: reference.file,
    sampleRate: reference.sampleRate, channels: reference.channels, frames: reference.frames,
    vehicle: identity.vehicle, license: source.license});
}

export function segmentFrames(reference, startSeconds, endSeconds) {
  validateRecordedReference(reference);
  const duration = reference.frames / reference.sampleRate;
  if (!Number.isFinite(startSeconds) || !Number.isFinite(endSeconds) ||
      startSeconds < 0 || endSeconds > duration + Number.EPSILON || endSeconds <= startSeconds)
    throw new Error('Invalid reference segment');
  const startFrame = Math.round(startSeconds * reference.sampleRate);
  const endFrame = Math.min(reference.frames, Math.round(endSeconds * reference.sampleRate));
  if (startFrame < 0 || endFrame > reference.frames || endFrame <= startFrame)
    throw new Error('Reference segment outside source');
  return {startFrame, endFrame};
}

const digestBytes = async bytes => {
  if (!globalThis.crypto?.subtle) throw new Error('Browser SHA-256 unavailable');
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
};

export class RecordedReferencePlayer {
  constructor(reference, fetchImpl=globalThis.fetch, base=new URL('../', import.meta.url), documentImpl=globalThis.document) {
    validateRecordedReference(reference);
    if (!/^[0-9a-f]{64}$/.test(reference.sha256||'')) throw new Error('Reference SHA-256 required');
    this.reference=reference;this.fetchImpl=fetchImpl;this.base=base;this.documentImpl=documentImpl;this.verified=false;this.url=null;
  }
  async prepare() {
    if (this.verified) return;
    const response=await this.fetchImpl(new URL(this.reference.file,this.base));
    if (!response.ok) throw new Error(`Reference fetch failed: ${response.status}`);
    const bytes=await response.arrayBuffer();
    if (await digestBytes(bytes) !== this.reference.sha256) throw new Error('Reference SHA-256 mismatch');
    this.bytes=bytes;
    this.verified=true;
  }
  async play() {
    await this.prepare();
    if (!this.documentImpl?.createElement) throw new Error('Document unavailable');
    return {bytes:this.bytes,verified:true,loop:false};
  }
}
