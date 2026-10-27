import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {ContinuousHybridRenderer} from '../src/continuous-hybrid.mjs';

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const finite = x => Number.isFinite(x);

export async function renderResearchComparison({texture, outDir, frames = 48000 * 10, sampleRate = 48000}) {
  if (!(texture instanceof Float32Array)) throw new Error('Research texture must be Float32Array');
  if (!Number.isSafeInteger(frames) || frames < sampleRate || frames > sampleRate * 60) throw new Error('Invalid research frame bound');
  await mkdir(outDir, {recursive: true});
  const renderer = new ContinuousHybridRenderer({sampleRate, texture, textureWeight: .35, base: ({load}) => .25 + load * .18});
  const output = new Float32Array(frames);
  let previous = 0, maxJump = 0;
  for (let i = 0; i < frames; i++) {
    const state = {rpm: 850 + 5000 * (i / Math.max(1, frames - 1)), load: i < frames / 2 ? .2 : .8, accel: i < frames / 2 ? 0 : 1.2};
    output[i] = renderer.next(state);
    if (!finite(output[i]) || Math.abs(output[i]) > 1) throw new Error('Research renderer unsafe output');
    if (i) maxJump = Math.max(maxJump, Math.abs(output[i] - previous));
    previous = output[i];
  }
  const bytes = Buffer.from(output.buffer, output.byteOffset, output.byteLength);
  let preClipPeak = 0;
  for (const sample of output) preClipPeak = Math.max(preClipPeak, Math.abs(sample));
  await writeFile(path.join(outDir, 'continuous-hybrid-research.f32le'), bytes);
  const receipt = {
    schema: 'vico.continuous-hybrid.research-receipt.v1',
    purpose: 'RESEARCH_ONLY_NOT_PRODUCT_AUDIO',
    sourceKind: 'PUBLIC_REAL_TEXTURE_UNKNOWN_STATE',
    frames, sampleRate, pcmSha256: sha256(bytes),
    textureFrames: texture.length, textureSha256: sha256(Buffer.from(texture.buffer, texture.byteOffset, texture.byteLength)),
    preClipPeak, maxSampleJump: maxJump,
    envelopeMin: renderer.envelopeMin, envelopeMax: renderer.envelopeMax,
    productCandidate: false, stateQualification: 'INSUFFICIENT_EVIDENCE',
  };
  await writeFile(path.join(outDir, 'continuous-hybrid-research.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  return receipt;
}

export async function readF32LE(pathname) {
  const bytes = await readFile(pathname);
  if (bytes.byteLength % 4) throw new Error('F32LE byte length mismatch');
  return new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
}
