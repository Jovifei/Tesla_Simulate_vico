import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {renderResearchComparison} from '../tools/continuous-hybrid-study.mjs';

test('research comparison emits bounded PCM with source identity and no product claim', async () => {
  const outDir = await mkdtemp(path.join(os.tmpdir(), 'vico-hybrid-study-'));
  const texture = Float32Array.from({length: 48000}, (_, i) => .15 * Math.sin(i / 11));
  const receipt = await renderResearchComparison({texture, outDir, frames: 48000});
  assert.equal(receipt.purpose, 'RESEARCH_ONLY_NOT_PRODUCT_AUDIO');
  assert.equal(receipt.productCandidate, false);
  assert.equal(receipt.stateQualification, 'INSUFFICIENT_EVIDENCE');
  assert(receipt.preClipPeak <= 1);
  const pcm = await readFile(path.join(outDir, 'continuous-hybrid-research.f32le'));
  assert.equal(pcm.length, 48000 * 4);
});

test('research comparison handles a multi-second PCM without spreading samples onto the call stack', async () => {
  const outDir = await mkdtemp(path.join(os.tmpdir(), 'vico-hybrid-study-long-'));
  const texture = Float32Array.from({length: 48000}, (_, i) => .15 * Math.sin(i / 11));
  const receipt = await renderResearchComparison({texture, outDir, frames: 48000 * 10});
  assert.equal(receipt.frames, 48000 * 10);
  assert(receipt.preClipPeak <= 1);
});
