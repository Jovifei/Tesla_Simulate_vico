import test from 'node:test';
import assert from 'node:assert/strict';
import {permittedPackage,loadV14Registry} from '../src/v14-registry.mjs';

const hash='a'.repeat(64);
const verified=()=>true;
const good=()=>({schema_version:'1.0',vehicles:[{legacy_key:'hellcat_v6',catalog_status:'TARGET_LOCKED',readiness_status:'ACOUSTIC_CALIBRATED',sound_packages:[{route_id:'a',package_id:'p',package_sha256:hash,owner_audition:{status:'PASS',route_id:'a',package_id:'p',package_sha256:hash,evidence_ref:'signed:1'}}]}]});
test('only the same qualified and signed package is selectable',()=>{
  assert.equal(permittedPackage(good(),'hellcat_v6',hash),false, 'self-asserted signature cannot unlock');
  assert.equal(permittedPackage(good(),'hellcat_v6',hash,verified),true);
  for(const mutate of [
    r=>delete r.vehicles[0].readiness_status,
    r=>r.vehicles[0].sound_packages[0].owner_audition.status='NOT_RUN',
    r=>r.vehicles[0].sound_packages[0].owner_audition.package_sha256='b'.repeat(64),
    r=>r.vehicles[0].sound_packages[0].owner_audition.evidence_ref=' ',
    r=>r.vehicles.push({...r.vehicles[0]})
  ]) {const r=good();mutate(r);assert.equal(permittedPackage(r,'hellcat_v6',hash,verified),false);}
  assert.equal(permittedPackage(good(),'hellcat_v6','b'.repeat(64)),false);
  assert.equal(permittedPackage(null,'hellcat_v6',hash),false);
});
test('missing fingerprint or bad source fails closed',async()=>{
  let called=false;const fetcher=async()=>{called=true;throw Error('bad hash')};
  assert.equal(await loadV14Registry(new URL('http://localhost/'),null,fetcher),null);
  assert.equal(called,false);
  assert.equal(await loadV14Registry(new URL('http://localhost/'),hash,fetcher),null);
});
