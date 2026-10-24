import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {buildSite,sha} from '../tools/build.mjs';
import {fixtureSources,wav} from './fixtures.mjs';

function pack(){
  const pcm=wav(new Float32Array(4800).fill(.25));
  return {pcm,attribution:'Fixture author\nhttps://example.test/start\nhttps://creativecommons.org/licenses/by-sa/4.0/\n',
    manifest:{schema:'vico.startup.pack.v1',vehicleKey:'hellcat_v6',file:'start.wav',sha256:sha(pcm),bytes:pcm.length,frames:4800,sampleRate:48000,fadeInMs:5,handoffMs:20,
      source:{author:'Fixture author',url:'https://example.test/start',license:'CC BY-SA 4.0',licenseUrl:'https://creativecommons.org/licenses/by-sa/4.0/',originalSHA256:'b'.repeat(64)},
      qualification:{level:'R2_RELATIVE_PUBLIC_REFERENCE',role:'ONE_SHOT_STARTUP',automaticTuningEligible:false,OEMQualification:false}}};
}
async function build(startupPack){const files=fixtureSources(),temp=await fs.mkdtemp(path.join(os.tmpdir(),'vico-start-build-')),out=path.join(temp,'dist');await buildSite({out,testOnly:true,webCommit:'TEST_FIXTURE',readBlob:async p=>files.get(p),startupPack});return {out,catalog:JSON.parse(await fs.readFile(path.join(out,'catalog.json')))};}
test('build binds a licensed one-shot to Hellcat only and publishes attribution',async()=>{
  const s=pack(),{out,catalog}=await build(s);
  for(const entry of catalog.vehicles){
    const bank=JSON.parse(await fs.readFile(path.join(out,entry.bankFile)));
    if(entry.id==='hellcat_v6'){
      assert.equal(bank.startup?.sha256,s.manifest.sha256);assert.equal(entry.startupAvailable,true);
      assert.equal(sha(await fs.readFile(path.join(out,'banks',entry.id,bank.startup.file))),s.manifest.sha256);
      assert.equal(bank.sourceCommit,'477913e7500bb3ff13c3b72cf5b1a3cac1b28145');
    }else assert.equal(bank.startup,undefined);
  }
  assert.match(await fs.readFile(path.join(out,'audio-credits.txt'),'utf8'),/Fixture author/);
});
test('build refuses modified data, missing rights and unknown vehicle startup packs',async()=>{
  for(const alter of [s=>s.pcm=Buffer.from('tampered'),s=>s.manifest.source.license='UNKNOWN',s=>s.manifest.vehicleKey='lfa',s=>s.attribution='']){
    const s=pack();alter(s);await assert.rejects(build(s));
  }
});
