import test from 'node:test';
import assert from 'node:assert/strict';
import {validateRecordedReference, segmentFrames} from '../src/recorded-reference.mjs';

const good = {
  schema: 'vico.recorded.reference.v1',
  scope: 'REFERENCE_ONLY',
  id: 'hellcat-startup-public',
  title: 'Hellcat startup public recording',
  file: 'hellcat-startup-original.wav',
  sampleRate: 48000,
  channels: 1,
  frames: 314306,
  source: {author: 'Axepas12', license: 'CC BY-SA 4.0', licenseUrl: 'https://creativecommons.org/licenses/by-sa/4.0/'},
  identity: {vehicle: 'Dodge Challenger Hellcat', state: 'UNKNOWN', synchronizedRpmLoad: false, OEMQualification: false},
  automaticLoop: false
};

test('validates a provenance-complete reference but rejects Hellcat relabeling', () => {
  const identity = validateRecordedReference(good);
  assert.equal(identity.scope, 'REFERENCE_ONLY');
  assert.equal(identity.id, good.id);
  const relabeled = structuredClone(good);
  relabeled.id = 'srt-public-preview';
  relabeled.title = 'Challenger SRT version unconfirmed';
  relabeled.file = 'srt-version-unconfirmed.wav';
  relabeled.sampleRate = 24000;
  relabeled.channels = 2;
  relabeled.frames = 5352000;
  relabeled.source = {author: 'JorisDJN', license: 'CC0', licenseUrl: 'https://creativecommons.org/publicdomain/zero/1.0/'};
  relabeled.identity = {vehicle: 'Dodge Challenger SRT (version unconfirmed)', state: 'UNKNOWN', synchronizedRpmLoad: false, OEMQualification: false};
  assert.equal(validateRecordedReference(relabeled).id, relabeled.id);
  assert.equal(relabeled.identity.vehicle, 'Dodge Challenger SRT (version unconfirmed)');
});

test('rejects incomplete provenance and product-qualified claims', () => {
  for (const mutation of [
    x => delete x.source.author,
    x => x.source.license = 'UNKNOWN',
    x => x.identity.OEMQualification = true,
    x => x.identity.synchronizedRpmLoad = true,
    x => x.automaticLoop = true,
    x => x.scope = 'PRODUCT_BANK',
    x => x.frames = 0
  ]) {
    const bad = structuredClone(good);
    mutation(bad);
    assert.throws(() => validateRecordedReference(bad));
  }
});

test('segment boundaries are integer source frames and stay inside the take', () => {
  assert.deepEqual(segmentFrames(good, 1.25, 2.75), {startFrame: 60000, endFrame: 132000});
  assert.deepEqual(segmentFrames(good, 0, 6.548041666666666), {startFrame: 0, endFrame: 314306});
  for (const [start, end] of [[-1, 1], [1, 7], [2, 2]]) {
    assert.throws(() => segmentFrames(good, start, end));
  }
});
