import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile, mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {buildSite, readStartupPack} from '../tools/build.mjs';
import {fixtureSources} from './fixtures.mjs';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');

test('build ships verified REFERENCE_ONLY sources with hashes and no product claims', async () => {
  const files = fixtureSources();
  const out = path.join(await mkdtemp(path.join(os.tmpdir(), 'vico-recorded-')), 'dist');
  const result = await buildSite({out, testOnly: true, readBlob: async relative => files.get(relative)});
  assert.equal(result.vehicles, 6);
  const manifest = JSON.parse(await readFile(path.join(out, 'recorded-references.json'), 'utf8'));
  assert.equal(manifest.schema, 'vico.recorded.reference.catalog.v1');
  assert.equal(manifest.scope, 'REFERENCE_ONLY');
  assert.equal(manifest.automaticLoop, false);
  assert.equal(manifest.qualification, 'SOURCE_TIMBRE_DIRECTION_ONLY_NOT_PRODUCT_OR_OEM');
  assert.deepEqual(manifest.references.map(x => x.id), ['hellcat-startup-public', 'srt-version-unconfirmed']);
  assert(manifest.references.every(x => x.identity.OEMQualification === false && x.identity.synchronizedRpmLoad === false));
  for (const reference of manifest.references) {
    const bytes = await readFile(path.join(out, 'assets', 'recorded-references', path.basename(reference.file)));
    assert.equal(sha(bytes), reference.sha256);
    assert.equal(bytes.length, reference.bytes);
  }
});
