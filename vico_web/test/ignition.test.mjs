import test from 'node:test';
import assert from 'node:assert/strict';

const moduleURL = new URL('../src/ignition.mjs', import.meta.url);
const {IgnitionSequence} = await import(moduleURL).catch(error => {
  if (error.code === 'ERR_MODULE_NOT_FOUND' && error.url === moduleURL.href) return {};
  throw error;
});
const SHA = 'a'.repeat(64);
const pcm = (values = [.125, .25, -.25, .5], sampleRate = 48000) => ({samples: Float32Array.from(values), sampleRate, sha256: SHA});
function sequence(asset = pcm(), outputRate = 48000) {
  assert.equal(typeof IgnitionSequence, 'function', 'IgnitionSequence export is required');
  return new IgnitionSequence(asset, outputRate);
}
function drain(player, owner, partitions = [128]) {
  const output = [];
  for (let block = 0; ; block++) {
    for (let i = 0; i < partitions[block % partitions.length]; i++) {
      const sample = player.next(owner);
      if (sample === null) return output;
      output.push(sample);
      assert(output.length < 1000000, 'one-shot sequence must terminate');
    }
  }
}

test('PCM sequence starts once for an owner and hands off after the final numeric frame', () => {
  const player = sequence();
  assert.equal(player.snapshot().stage, 'ready');
  assert.equal(player.next(1), null);
  assert.equal(player.start(1), true);
  assert.equal(player.start(1), false);
  assert.deepEqual(drain(player, 1), Array.from(pcm().samples));
  assert.equal(player.next(1), null);
  assert.equal(player.start(1), false);
  const status = player.snapshot();
  assert.equal(status.stage, 'ended');
  assert.equal(status.owner, 1);
  assert.equal(status.sourceFrames, 4);
  assert.equal(status.outputFrames, 4);
  assert.equal(status.ended, true);
  assert.equal(status.sha256, SHA);
});

test('zero is a valid PCM sample, never an end-of-sequence sentinel', () => {
  const player = sequence(pcm([0, .25, 0]));
  player.start(1);
  assert.deepEqual([player.next(1), player.next(1), player.next(1), player.next(1)], [0, .25, 0, null]);
});

test('explicit cancellation makes the current owner terminal until a new owner starts', () => {
  const player = sequence();
  player.start(1);
  assert.equal(player.next(1), .125);
  assert.equal(player.cancel(1), true);
  assert.equal(player.snapshot().stage, 'cancelled');
  assert.equal(player.snapshot().ended, true);
  assert.equal(player.next(1), null);
  assert.equal(player.start(1), false);
  assert.equal(player.start(2), true);
  assert.equal(player.next(2), .125);
  assert.equal(player.cancel(), true);
  assert.equal(player.next(2), null);
});

test('a fresh owner replaces the old sequence from frame zero without an old-owner read advancing it', () => {
  const player = sequence();
  assert.equal(player.start(10), true);
  player.next(10);
  player.next(10);
  assert.equal(player.start(11), true);
  for (let i = 0; i < 100; i++) assert.equal(player.next(10), null);
  assert.equal(player.snapshot().outputFrames, 0);
  assert.equal(player.cancel(10), false);
  assert.equal(player.next(11), .125);
  assert.equal(player.start(10), false);
  assert.equal(player.next(11), .25);
  assert.equal(player.start(12), true);
  assert.deepEqual(drain(player, 12), Array.from(pcm().samples));
});

test('invalid and obsolete owner identifiers cannot start, cancel, or advance the player', () => {
  const player = sequence();
  for (const owner of [undefined, null, 0, -1, 1.5, NaN, Infinity, '1', Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(player.start(owner), false);
    assert.equal(player.next(owner), null);
    assert.equal(player.cancel(owner), false);
  }
  assert.equal(player.start(2), true);
  assert.equal(player.start(1), false);
  assert.equal(player.next(1, true), null);
  assert.equal(player.next(2), .125);
  assert.equal(player.start(Number.MAX_SAFE_INTEGER), true);
});

test('mute cancels immediately and restoring audibility cannot resume an old startup', () => {
  const player = sequence();
  player.start(1);
  assert.equal(player.next(1), .125);
  assert.equal(player.next(1, true), 0);
  assert.equal(player.snapshot().stage, 'cancelled');
  assert.equal(player.snapshot().outputFrames, 1);
  for (let i = 0; i < 20; i++) assert.equal(player.next(1, true), null);
  assert.equal(player.next(1, false), null);
  assert.equal(player.start(1), false);
  assert.equal(player.start(2), true);
  assert.equal(player.next(2), .125);
});

test('absent PCM is explicitly unavailable and never creates a synthetic startup', () => {
  for (const asset of [undefined, null]) {
    assert.equal(typeof IgnitionSequence, 'function', 'IgnitionSequence export is required');
    const player = new IgnitionSequence(asset, 48000);
    assert.equal(player.snapshot().stage, 'unavailable');
    assert.equal(player.snapshot().sourceFrames, 0);
    assert.equal(player.snapshot().outputFrames, 0);
    assert.equal(player.snapshot().ended, true);
    assert.equal(player.start(1), false);
    assert.equal(player.next(1), null);
    assert.equal(player.cancel(), false);
  }
});

test('linear interpolation follows the source clock at 44.1/48/96 kHz without quantum boundaries', () => {
  const samples = Float32Array.from({length: 10007}, (_, i) => .4 * Math.sin(i * .017));
  for (const rate of [44100, 48000, 96000]) {
    const asset = {samples, sampleRate: 48000};
    const a = sequence(asset, rate), b = sequence(asset, rate);
    a.start(1); b.start(1);
    const expected = drain(a, 1, [1]);
    assert.deepEqual(drain(b, 1, [128, 1, 257, 64, 511]), expected);
    for (let frame = 0; frame < expected.length; frame++) {
      const position = frame * 48000 / rate;
      const left = Math.min(Math.floor(position), samples.length - 1);
      const right = Math.min(left + 1, samples.length - 1);
      const value = Math.fround(samples[left] + (samples[right] - samples[left]) * (position - left));
      assert.equal(expected[frame], value);
    }
  }
});

test('duration error stays below one output frame and the first post-duration read hands off', () => {
  for (const sourceRate of [48000, 96000]) {
    for (const rate of [44100, 48000, 96000]) {
      for (const count of [1, 2, 11, 4801, 48000]) {
        const player = sequence({samples: new Float32Array(count).fill(.25), sampleRate: sourceRate}, rate);
        player.start(1);
        const frames = Math.ceil(count * rate / sourceRate);
        for (let frame = 0; frame < frames; frame++) assert.equal(player.next(1), .25);
        assert.equal(player.snapshot().outputFrames, frames);
        assert.equal(player.snapshot().stage, 'ended');
        assert.equal(player.next(1), null);
        assert.equal(player.next(1), null);
        assert(frames / rate - count / sourceRate >= -Number.EPSILON);
        assert(frames / rate - count / sourceRate < 1 / rate + Number.EPSILON);
      }
    }
  }
});

test('the final source frame is preserved and held only for the fractional output tail', () => {
  const player = sequence(pcm([.25, .5]), 96000);
  player.start(1);
  assert.deepEqual(drain(player, 1), [.25, .375, .5, .5]);
  const single = sequence(pcm([-.5]), 44100);
  single.start(1);
  assert.deepEqual(drain(single, 1), [-.5]);
});

test('construction owns the validated PCM and metadata independently of caller mutation', () => {
  const asset = pcm();
  const player = sequence(asset);
  asset.samples[0] = NaN;
  asset.samples.fill(0);
  asset.sampleRate = 96000;
  asset.sha256 = 'changed';
  player.start(1);
  assert.deepEqual(drain(player, 1), [.125, .25, -.25, .5]);
  assert.equal(player.snapshot().sha256, SHA);
});

test('malformed PCM format, empty data, and oversize buffers are rejected before playback', () => {
  sequence();
  for (const asset of [{}, [], 'pcm', {samples: [0], sampleRate: 48000},
    {samples: new Float64Array([0]), sampleRate: 48000},
    {samples: new Int16Array([0]), sampleRate: 48000},
    {samples: new Float32Array(), sampleRate: 48000},
    {samples: new Float32Array(2 * 1024 * 1024 + 1), sampleRate: 48000}]) {
    assert.throws(() => sequence(asset), /PCM|asset|format|bound/i);
  }
});

test('non-finite PCM, invalid sample rates, and malformed hash tokens are rejected', () => {
  sequence();
  for (const value of [NaN, Infinity, -Infinity]) assert.throws(() => sequence(pcm([0, value])), /finite|PCM/i);
  for (const rate of [undefined, null, 0, -48000, NaN, Infinity, '48000', 48000.5, 7999, 192001]) {
    assert.throws(() => sequence({samples: new Float32Array([0]), sampleRate: rate}), /rate/i);
  }
  for (const rate of [undefined, null, 0, -48000, NaN, Infinity, '48000', 48000.5, 15999, 192001]) {
    assert.throws(() => new IgnitionSequence(pcm(), rate), /rate/i);
  }
  for (const sha256 of [null, '', 'A'.repeat(64), 'a'.repeat(63), 'g'.repeat(64), 123]) {
    assert.throws(() => sequence({...pcm(), sha256}), /SHA|hash/i);
  }
});
