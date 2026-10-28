import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {ContinuousHybridRenderer} from '../src/continuous-hybrid.mjs';

const ROUTES = ['RECORDED_PRIMARY', 'LEGACY_BANK', 'GENERIC_PHYSICS'];
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
const sha256 = value => createHash('sha256').update(value).digest('hex');

export function researchTrace(sampleRate = 48000) {
  return {schema: 'vico.research-three-way-trace.v1', sampleRate, durationS: 60, resetCount: 0,
    segments: [{condition: 'idle', durationS: 15}, {condition: 'acceleration', durationS: 15},
      {condition: 'high-rpm', durationS: 15}, {condition: 'coast', durationS: 10}, {condition: 'idle', durationS: 5}]};
}

function states(frames) {
  return Array.from({length: frames}, (_, i) => {
    const t = i / 48000;
    const rpm = t < 15 ? 850 : t < 30 ? 850 + (t - 15) / 15 * 4500 : t < 45 ? 5350 : t < 55 ? 5350 - (t - 45) / 10 * 3800 : 1550 - (t - 55) / 5 * 700;
    const load = t < 15 ? .18 : t < 30 ? .18 + (t - 15) / 15 * .62 : t < 45 ? .8 : t < 55 ? .8 - (t - 45) / 10 * .65 : .15;
    const accel = t >= 15 && t < 30 ? 1.2 : t >= 45 && t < 55 ? -1.2 : 0;
    return {rpm, load, accel};
  });
}

function renderLegacy(trajectory) {
  const frames = trajectory.length;
  const out = new Float32Array(frames);
  let phase = 0;
  for (let i = 0; i < frames; i++) { const s = trajectory[i]; phase += s.rpm / 120 / 48000; out[i] = Math.fround(Math.sin(2 * Math.PI * phase) * (.18 + .28 * s.load)); }
  return out;
}

function renderGeneric(trajectory) {
  const frames = trajectory.length;
  const out = new Float32Array(frames);
  let phase = 0;
  for (let i = 0; i < frames; i++) { const s = trajectory[i]; phase += s.rpm / 120 / 48000; const amp = .15 + .35 * s.load; out[i] = Math.fround((Math.sin(2 * Math.PI * phase) + .32 * Math.sin(4 * Math.PI * phase) + .12 * Math.sin(8 * Math.PI * phase)) * amp); }
  return out;
}

function stats(samples) {
  let peak = 0, sum = 0, maxJump = 0, previous = 0;
  for (let i = 0; i < samples.length; i++) { const v = samples[i]; peak = Math.max(peak, Math.abs(v)); sum += v * v; if (i) maxJump = Math.max(maxJump, Math.abs(v - previous)); previous = v; }
  return {frames: samples.length, rms: Math.sqrt(sum / samples.length), peak, maxSampleJump: maxJump};
}

export async function compareResearchRoutes({texture, textureSha256, outDir, sampleRate = 48000}) {
  if (!(texture instanceof Float32Array) || texture.length < sampleRate) throw new Error('Research texture is missing or too short');
  const trace = researchTrace(sampleRate), frames = sampleRate * trace.durationS, trajectory = states(frames);
  await mkdir(outDir, {recursive: true});
  const hybrid = new ContinuousHybridRenderer({sampleRate, texture, textureWeight: .35, base: ({load}) => .18 + .16 * load});
  const recorded = new Float32Array(frames);
  const legacy = renderLegacy(trajectory);
  const generic = renderGeneric(trajectory);
  for (let i = 0; i < frames; i++) recorded[i] = hybrid.next(trajectory[i]);
  const routes = [{id: 'recorded-primary', provenance: 'RECORDED_PRIMARY', samples: recorded}, {id: 'legacy-bank', provenance: 'LEGACY_BANK', samples: legacy}, {id: 'generic-physics', provenance: 'GENERIC_PHYSICS', samples: generic}];
  const metrics = routes.map(route => ({id: route.id, provenance: route.provenance, ...stats(route.samples), pcmSha256: sha256(Buffer.from(route.samples.buffer))}));
  const receipt = {schema: 'vico.research-three-way-receipt.v1', purpose: 'RESEARCH_ONLY_NOT_PRODUCT_AUDIO', stateQualification: 'INSUFFICIENT_EVIDENCE', productCandidate: false, trace, textureSha256, routes: metrics};
  await writeFile(path.join(outDir, 'three-way-research.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  return receipt;
}
