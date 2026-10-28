import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {compareResearchRoutes, researchTrace} from '../tools/research-three-way-comparator.mjs';

test('research three-way comparator keeps identities separate and never creates a product candidate', async () => {
  const outDir = await mkdtemp(path.join(os.tmpdir(), 'vico-three-way-research-'));
  const texture = Float32Array.from({length: 48000}, (_, i) => .12 * Math.sin(i / 19));
  const receipt = await compareResearchRoutes({texture, textureSha256: 'a'.repeat(64), outDir});
  assert.deepEqual(receipt.routes.map(route => route.provenance), ['RECORDED_PRIMARY', 'LEGACY_BANK', 'GENERIC_PHYSICS']);
  assert.equal(receipt.trace.durationS, 60);
  assert.equal(receipt.trace.resetCount, 0);
  assert.equal(receipt.stateQualification, 'INSUFFICIENT_EVIDENCE');
  assert.equal(receipt.productCandidate, false);
  assert(receipt.routes.every(route => route.frames === 60 * 48000 && route.peak <= 1 && route.maxSampleJump < .5));
  assert.equal(JSON.parse(await readFile(path.join(outDir, 'three-way-research.json'), 'utf8')).routes.length, 3);
});

test('research trace has the fixed five-segment timeline', () => {
  const trace = researchTrace();
  assert.deepEqual(trace.segments.map(segment => segment.condition), ['idle', 'acceleration', 'high-rpm', 'coast', 'idle']);
  assert.equal(trace.segments.reduce((sum, segment) => sum + segment.durationS, 0), 60);
});
