import test from 'node:test';
import assert from 'node:assert/strict';
import {ContinuousTextureReader, ContinuousHybridRenderer, makeRaisedCosineEvent} from '../src/continuous-hybrid.mjs';

function texture() {
  const x = new Float32Array(48000);
  for (let i = 0; i < x.length; i++) x[i] = Math.fround(.18 * Math.sin(2 * Math.PI * i / 173) + .04 * Math.sin(2 * Math.PI * i / 37));
  return x;
}

test('texture reader preserves one phase clock across arbitrary output block sizes', () => {
  const a = new ContinuousTextureReader(texture(), 48000);
  const b = new ContinuousTextureReader(texture(), 48000);
  const expected = new Float32Array(12000);
  const actual = new Float32Array(12000);
  for (let i = 0; i < expected.length; i++) expected[i] = a.next(1800);
  let at = 0, index = 0;
  const sizes = [1, 17, 128, 960, 997, 31];
  while (at < actual.length) {
    const size = sizes[index++ % sizes.length];
    const end = Math.min(actual.length, at + size);
    while (at < end) actual[at++] = b.next(1800);
  }
  assert.deepEqual(actual, expected);
  assert.equal(a.phase, b.phase);
});

test('texture reader never seeks when RPM/load state changes', () => {
  const reader = new ContinuousTextureReader(texture(), 48000);
  for (let i = 0; i < 1000; i++) reader.next(900);
  const before = reader.phase;
  for (let i = 0; i < 1000; i++) reader.next(4200);
  assert(reader.phase > before);
  assert.equal(reader.resets, 0);
});

test('hybrid envelope is smoothed and output remains bounded', () => {
  const renderer = new ContinuousHybridRenderer({
    sampleRate: 48000,
    texture: texture(),
    textureWeight: .45,
    base: () => .22,
  });
  const out = [];
  for (let i = 0; i < 2400; i++) out.push(renderer.next({rpm: 900, load: i < 1200 ? 0 : 1, accel: i < 1200 ? 0 : 1}));
  assert(out.every(x => Number.isFinite(x) && Math.abs(x) <= 1));
  assert(renderer.envelopeMin > 0);
  assert(renderer.envelopeMax < 1);
  assert(Math.max(...out.slice(1).map((x, i) => Math.abs(x - out[i]))) < .2);
});

test('events use bounded attack and release envelopes without a hard reset', () => {
  const event = makeRaisedCosineEvent(Float32Array.from([.8, .4, -.4, -.8]), 16);
  const renderer = new ContinuousHybridRenderer({sampleRate: 48000, texture: texture(), textureWeight: 0, base: () => 0});
  renderer.trigger(event);
  const out = Array.from({length: 32}, () => renderer.next({rpm: 1000, load: .5, accel: 0}));
  assert.equal(out[0], 0);
  assert(out.some(x => Math.abs(x) > .01));
  assert.equal(out.at(-1), 0);
  assert(out.every(x => Math.abs(x) <= 1));
});

test('missing texture is an explicit zero-weight layer, not an invented waveform', () => {
  const renderer = new ContinuousHybridRenderer({sampleRate: 48000, texture: null, base: () => .125});
  const out = Array.from({length: 10}, () => renderer.next({rpm: 1000, load: .4, accel: 0}));
  assert(out.every(x => Number.isFinite(x) && Math.abs(x) <= 1));
  assert.equal(renderer.textureWeight, 0);
});
