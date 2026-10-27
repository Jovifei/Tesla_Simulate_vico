import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {validateRecordedStateContract} from './recorded-state-contract.mjs';

const ROUTES = [
  {id: 'recorded-primary', label: 'RECORDED_PRIMARY', key: 'recordedPrimary'},
  {id: 'legacy-bank', label: 'LEGACY_BANK', key: 'legacyBank'},
  {id: 'generic-physics', label: 'GENERIC_PHYSICS', key: 'genericPhysics'},
];

export function fixedStudyTrace() {
  return {
    schema: 'vico.three-way-study-trace.v1', durationS: 60, sampleRateHz: 100, resetCount: 0,
    segments: [
      {condition: 'idle', durationS: 15},
      {condition: 'acceleration', durationS: 15},
      {condition: 'high-rpm', durationS: 15},
      {condition: 'coast', durationS: 10},
      {condition: 'idle', durationS: 5},
    ],
  };
}

function sha256(value) { return createHash('sha256').update(value).digest('hex'); }

function routeReceipt(route, result) {
  if (!result || !(result.samples instanceof Float32Array) || typeof result.provenance !== 'string') {
    throw new Error(`${route.id} renderer must return Float32Array samples and provenance`);
  }
  if (result.samples.length !== 60 * 48000) throw new Error(`${route.id} renderer must return the full 60-second 48 kHz trace`);
  for (const sample of result.samples) {
    if (!Number.isFinite(sample) || Math.abs(sample) > 1) throw new Error(`${route.id} renderer returned unsafe PCM`);
  }
  return {id: route.id, provenance: result.provenance, frames: result.samples.length,
    sha256: sha256(Buffer.from(result.samples.buffer, result.samples.byteOffset, result.samples.byteLength)), samples: result.samples};
}

export async function runThreeWayOfflineStudy({contract, outDir, renderers = {}}) {
  if (!outDir) throw new Error('outDir is required');
  await mkdir(outDir, {recursive: true});
  const qualification = validateRecordedStateContract(contract);
  const trace = fixedStudyTrace();
  const receipt = {
    schema: 'vico.three-way-study-receipt.v1', status: qualification.status,
    contractStatus: qualification, trace, routes: ROUTES.map(({id, label}) => ({id, provenance: label, rendered: false})),
    pcmWritten: false, productCandidate: false, reasons: [...qualification.reasons],
  };
  if (qualification.status !== 'ELIGIBLE') {
    await writeFile(path.join(outDir, 'study-receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    return {status: receipt.status, renderedRoutes: [], productCandidate: false, receipt};
  }
  const renderedRoutes = [];
  for (const route of ROUTES) {
    const renderer = renderers[route.key];
    if (typeof renderer !== 'function') {
      receipt.reasons.push(`${route.id} renderer is not provided`);
      await writeFile(path.join(outDir, 'study-receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
      return {status: 'INSUFFICIENT_EVIDENCE', renderedRoutes: [], productCandidate: false, receipt};
    }
    try {
      renderedRoutes.push(routeReceipt(route, await renderer({contract, trace, route})));
    } catch (error) {
      receipt.reasons.push(error instanceof Error ? error.message : `${route.id} renderer failed`);
      await writeFile(path.join(outDir, 'study-receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
      return {status: 'INSUFFICIENT_EVIDENCE', renderedRoutes: [], productCandidate: false, receipt};
    }
  }
  const publishedRoutes = [];
  for (const route of renderedRoutes) {
    const outputFile = `${route.id}.f32le`;
    await writeFile(path.join(outDir, outputFile), Buffer.from(route.samples.buffer, route.samples.byteOffset, route.samples.byteLength));
    publishedRoutes.push({...route, outputFile, rendered: true});
    delete route.samples;
  }
  receipt.routes = publishedRoutes;
  receipt.pcmWritten = true;
  receipt.productCandidate = false;
  receipt.reasons.push('human, device, and acoustic qualification remain open');
  await writeFile(path.join(outDir, 'study-trace.json'), `${JSON.stringify(trace, null, 2)}\n`, 'utf8');
  await writeFile(path.join(outDir, 'study-receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  return {status: receipt.status, renderedRoutes: publishedRoutes, productCandidate: false, receipt};
}

export function rendererReceiptBytes(samples) {
  if (!(samples instanceof Float32Array)) throw new TypeError('renderer samples must be Float32Array');
  return {frames: samples.length, sha256: sha256(Buffer.from(samples.buffer, samples.byteOffset, samples.byteLength))};
}
