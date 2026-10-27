import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {runThreeWayOfflineStudy, fixedStudyTrace} from '../tools/three-way-offline-study.mjs';

function incompleteContract() {
  return {schema: 'vico.recorded.state-contract.v1', vehicleKey: 'hellcat_v6', source: {
    sourceId: 'unknown-startup', originalSha256: 'a'.repeat(64), pcmSha256: 'b'.repeat(64),
    format: {sampleRate: 48000, channels: 1, encoding: 'F32LE'},
    license: {spdx: 'CC-BY-SA-4.0', redistributionAllowed: true, attribution: 'test'},
    capture: {micPosition: 'unknown', environment: 'unknown'}
  }, regions: [], holdout: {regionIds: [], independent: false, sourceSha256: 'c'.repeat(64)}};
}

function eligibleContract() {
  const c = incompleteContract();
  c.source.capture = {micPosition: 'tailpipe-left', environment: 'dyno-room'};
  const region = (id, role, startFrame, endFrame, hash) => ({
    id, role, condition: 'idle', startFrame, endFrame,
    stateTrace: {sha256: hash.repeat(64), sampleRateHz: 100, rows: 100, synchronizedToPcm: true},
    state: {rpm: 'MEASURED', load: 'MEASURED', gear: 'MEASURED', phase720: {source: 'MEASURED', verified: true}},
  });
  c.regions = [region('idle-train', 'train', 0, 48000, 'd'), region('pull-train', 'train', 48000, 96000, 'e'),
    region('coast-train', 'train', 96000, 144000, 'a'), region('holdout', 'holdout', 144000, 192000, 'c')];
  c.regions[1].condition = 'loaded-pull';
  c.regions[2].condition = 'coast';
  c.holdout = {regionIds: ['holdout'], independent: true, sourceSha256: 'f'.repeat(64)};
  return c;
}

test('fixed trace has one continuous 60-second clock and no reset', () => {
  const trace = fixedStudyTrace();
  assert.equal(trace.durationS, 60);
  assert.equal(trace.segments.map(segment => segment.durationS).reduce((a, b) => a + b, 0), 60);
  assert.equal(trace.resetCount, 0);
  assert.deepEqual(trace.segments.map(segment => segment.condition), ['idle', 'acceleration', 'high-rpm', 'coast', 'idle']);
});

test('incomplete source produces a receipt and no fake PCM or product candidate', async () => {
  const outDir = await mkdtemp(path.join(os.tmpdir(), 'vico-state-study-'));
  const result = await runThreeWayOfflineStudy({contract: incompleteContract(), outDir});
  assert.equal(result.status, 'INSUFFICIENT_EVIDENCE');
  assert.equal(result.renderedRoutes.length, 0);
  assert.equal(result.productCandidate, false);
  const receipt = JSON.parse(await readFile(path.join(outDir, 'study-receipt.json'), 'utf8'));
  assert.equal(receipt.status, 'INSUFFICIENT_EVIDENCE');
  assert.equal(receipt.pcmWritten, false);
  assert.equal(receipt.routes.length, 3);
  assert(receipt.reasons.length > 0);
});

test('eligible study requires all three explicit renderers and keeps route identities separate', async () => {
  const outDir = await mkdtemp(path.join(os.tmpdir(), 'vico-state-study-'));
  const contract = eligibleContract();
  const routes = {
    recordedPrimary: async () => ({frames: 60, sha256: '1'.repeat(64), provenance: 'RECORDED_PRIMARY'}),
    legacyBank: async () => ({frames: 60, sha256: '2'.repeat(64), provenance: 'LEGACY_BANK'}),
    genericPhysics: async () => ({frames: 60, sha256: '3'.repeat(64), provenance: 'GENERIC_PHYSICS'})
  };
  const result = await runThreeWayOfflineStudy({contract, outDir, renderers: routes});
  assert.equal(result.status, 'INSUFFICIENT_EVIDENCE');
  assert.equal(result.renderedRoutes.length, 0);
});

test('eligible study writes only real Float32 PCM returned by each route', async () => {
  const outDir = await mkdtemp(path.join(os.tmpdir(), 'vico-state-study-'));
  const samples = label => { const x = new Float32Array(60 * 48000); x.fill(label); return x; };
  const result = await runThreeWayOfflineStudy({contract: eligibleContract(), outDir, renderers: {
    recordedPrimary: async () => ({samples: samples(0.1), provenance: 'RECORDED_PRIMARY'}),
    legacyBank: async () => ({samples: samples(0.2), provenance: 'LEGACY_BANK'}),
    genericPhysics: async () => ({samples: samples(0.3), provenance: 'GENERIC_PHYSICS'}),
  }});
  assert.equal(result.status, 'ELIGIBLE');
  assert.equal(result.renderedRoutes.length, 3);
  assert.equal(result.productCandidate, false);
  for (const route of result.renderedRoutes) {
    assert.equal(route.frames, 60 * 48000);
    assert.match(route.outputFile, /\.f32le$/);
    assert.equal((await readFile(path.join(outDir, route.outputFile))).length, 60 * 48000 * 4);
  }
});
