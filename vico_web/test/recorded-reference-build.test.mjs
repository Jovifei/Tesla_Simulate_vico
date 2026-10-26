import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile, mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {buildSite, readRecordedReferences} from '../tools/build.mjs';
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
  assert.deepEqual(manifest.references.map(x => x.id), ['hellcat-startup-public', 'srt-version-unconfirmed',
    'candidate-idle-low-35-55', 'candidate-accel-63-69', 'candidate-accel-108-114',
    'candidate-accel-153-159', 'candidate-offload-160-170', 'candidate-sustained-185-195']);
  assert(manifest.references.every(x => x.identity.OEMQualification === false && x.identity.synchronizedRpmLoad === false));
  assert(manifest.references.slice(2).every(x=>/^原录音 \d+–\d+ 秒$/.test(x.title)));
  assert(manifest.references.slice(2).every(x=>x.sourceSegment?.parentSha256==='a7fd478c1508308d0dce953763609dc5852819bf2f29a8d4c1972ca0d11450bd'));
  for (const reference of manifest.references) {
    const bytes = await readFile(path.join(out, 'assets', 'recorded-references', path.basename(reference.file)));
    assert.equal(sha(bytes), reference.sha256);
    assert.equal(bytes.length, reference.bytes);
  }
});

test('build rejects changed accepted PCM and SRT relabeling before publication',async()=>{
  const references=await readRecordedReferences(),files=fixtureSources();
  for(const change of [
    rows=>{rows[0].pcm=Buffer.from(rows[0].pcm);rows[0].pcm[100]^=1;},
    rows=>{rows[1].reference={...rows[1].reference,identity:{...rows[1].reference.identity,vehicle:'Dodge Challenger Hellcat'}};}
  ]){
    const rows=references.map(row=>({...row}));change(rows);
    const out=path.join(await mkdtemp(path.join(os.tmpdir(),'vico-recorded-tamper-')),'dist');
    await assert.rejects(buildSite({out,testOnly:true,recordedReferences:rows,readBlob:async relative=>files.get(relative)}),/identity|SHA-256/);
  }
});
