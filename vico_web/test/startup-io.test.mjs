import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {loadBank} from '../src/session.mjs';
import {spec,wav} from './fixtures.mjs';

const sha=x=>createHash('sha256').update(x).digest('hex');
function bankData(){
  const pcm=wav(new Float32Array(4800).fill(.2));
  const row={file:`asset-${sha(pcm)}.wav`,sha256:sha(pcm),bytes:pcm.length,frames:4800};
  const d={schema:'vico.web.bank.v1',vehicleKey:'hellcat_v6',sampleRate:48000,spec,loops:[{rpm:700,load:.32,...row}],afterfire:row,shifts:[],
    startup:{...row,sampleRate:48000,fadeInMs:5,handoffMs:20,source:{author:'fixture',url:'https://example.test/start',license:'CC BY-SA 4.0',licenseUrl:'https://creativecommons.org/licenses/by-sa/4.0/',originalSHA256:'b'.repeat(64)},qualification:{level:'R2_RELATIVE_PUBLIC_REFERENCE',OEMQualification:false}}};
  return {d,pcm};
}
async function load(d,pcm){
  const bytes=Buffer.from(JSON.stringify(d)),old=globalThis.fetch;
  globalThis.fetch=async url=>new Response(String(url).endsWith('bank.json')?bytes:pcm);
  try{return await loadBank({id:'hellcat_v6',bankFile:'banks/hellcat_v6/bank.json',bankSha256:sha(bytes)},new URL('http://localhost/'));}
  finally{globalThis.fetch=old;}
}
test('loader verifies and exposes actual one-shot PCM separately from frozen event arrays',async()=>{
  const {d,pcm}=bankData(),b=await load(d,pcm);
  assert(b.startup?.samples instanceof Float32Array);
  assert.equal(b.startup.samples.length,4800);assert.equal(b.startup.sha256,d.startup.sha256);
  assert.equal(b.shifts.length,0);assert.equal(b.identity.startupSHA256,d.startup.sha256);
});
test('missing startup is an explicit unavailable bank, not a generated imitation',async()=>{
  const {d,pcm}=bankData();delete d.startup;assert.equal((await load(d,pcm)).startup,null);
});
test('startup digest, length, rate, attribution and numeric contract are enforced',async()=>{
  for(const mutation of [s=>s.sha256='c'.repeat(64),s=>s.frames++,s=>s.sampleRate=96000,s=>s.source.author='',s=>s.source.license='UNKNOWN']){
    const {d,pcm}=bankData();mutation(d.startup);await assert.rejects(load(d,pcm));
  }
  const {d}=bankData(),pcm=wav(new Float32Array(4800).fill(2));d.startup.sha256=sha(pcm);d.startup.file=`asset-${sha(pcm)}.wav`;d.startup.bytes=pcm.length;
  await assert.rejects(load(d,pcm));
});
