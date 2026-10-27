import test from 'node:test';
import assert from 'node:assert/strict';
import {validateRecordedStateContract} from '../tools/recorded-state-contract.mjs';

function completeContract() {
  return {
    schema: 'vico.recorded.state-contract.v1',
    vehicleKey: 'hellcat_v6',
    source: {
      sourceId: 'hellcat-test-capture',
      originalSha256: 'a'.repeat(64),
      pcmSha256: 'b'.repeat(64),
      format: {sampleRate: 48000, channels: 1, encoding: 'F32LE'},
      license: {spdx: 'CC-BY-SA-4.0', redistributionAllowed: true, attribution: 'test'},
      capture: {micPosition: 'tailpipe-left', environment: 'dyno-room'}
    },
    regions: [
      {id: 'idle-train', role: 'train', condition: 'idle', startFrame: 0, endFrame: 48000,
        stateTrace: {sha256: 'c'.repeat(64), sampleRateHz: 100, rows: 100, synchronizedToPcm: true},
        state: {rpm: 'MEASURED', load: 'MEASURED', gear: 'MEASURED', phase720: {source: 'MEASURED', verified: true}}},
      {id: 'pull-train', role: 'train', condition: 'loaded-pull', startFrame: 48000, endFrame: 144000,
        stateTrace: {sha256: 'd'.repeat(64), sampleRateHz: 100, rows: 200, synchronizedToPcm: true},
        state: {rpm: 'MEASURED', load: 'MEASURED', gear: 'MEASURED', phase720: {source: 'MEASURED', verified: true}}},
      {id: 'coast-train', role: 'train', condition: 'coast', startFrame: 144000, endFrame: 192000,
        stateTrace: {sha256: 'e'.repeat(64), sampleRateHz: 100, rows: 100, synchronizedToPcm: true},
        state: {rpm: 'MEASURED', load: 'MEASURED', gear: 'MEASURED', phase720: {source: 'MEASURED', verified: true}}},
      {id: 'idle-holdout', role: 'holdout', condition: 'idle', startFrame: 192000, endFrame: 240000,
        stateTrace: {sha256: 'e'.repeat(64), sampleRateHz: 100, rows: 100, synchronizedToPcm: true},
        state: {rpm: 'MEASURED', load: 'MEASURED', gear: 'MEASURED', phase720: {source: 'MEASURED', verified: true}}}
    ],
    holdout: {regionIds: ['idle-holdout'], independent: true, sourceSha256: 'f'.repeat(64)}
  };
}

test('complete measured contract is eligible and preserves source identity', () => {
  const result = validateRecordedStateContract(completeContract());
  assert.equal(result.status, 'ELIGIBLE');
  assert.equal(result.vehicleKey, 'hellcat_v6');
  assert.equal(result.trainingRegionCount, 3);
  assert.equal(result.holdoutRegionCount, 1);
});

test('missing measured state fails closed without inventing RPM or load', () => {
  const contract = completeContract();
  contract.regions[1].state.load = 'UNKNOWN';
  const result = validateRecordedStateContract(contract);
  assert.equal(result.status, 'INSUFFICIENT_EVIDENCE');
  assert(result.reasons.some(reason => /load/i.test(reason)));
  assert(!('estimatedLoad' in result));
});

test('missing license, phase, synchronization, or independent holdout is rejected', () => {
  for (const mutate of [
    c => { delete c.source.license; },
    c => { c.regions[0].state.phase720 = {source: 'INFERRED', verified: false}; },
    c => { c.regions[0].stateTrace.synchronizedToPcm = false; },
    c => { c.holdout.independent = false; },
    c => { c.holdout.regionIds = []; },
  ]) {
    const contract = completeContract();
    mutate(contract);
    assert.equal(validateRecordedStateContract(contract).status, 'INSUFFICIENT_EVIDENCE');
  }
});

test('overlapping regions and non-monotonic frame boundaries are rejected', () => {
  const contract = completeContract();
  contract.regions[1].startFrame = 40000;
  assert.equal(validateRecordedStateContract(contract).status, 'INSUFFICIENT_EVIDENCE');
  const nonMonotonic = completeContract();
  nonMonotonic.regions[2].endFrame = nonMonotonic.regions[2].startFrame;
  assert.equal(validateRecordedStateContract(nonMonotonic).status, 'INSUFFICIENT_EVIDENCE');
});
