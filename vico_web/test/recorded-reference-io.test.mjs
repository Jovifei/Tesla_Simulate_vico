import test from 'node:test';
import assert from 'node:assert/strict';

const bytes=bytesFrom=>bytesFrom;
test('reference catalog fetch verifies every source SHA and rejects product claims',async()=>{
  const {loadRecordedReferenceCatalog}=await import('../src/session.mjs');
  const good=Buffer.from(JSON.stringify({
    schema:'vico.recorded.reference.catalog.v1',scope:'REFERENCE_ONLY',automaticLoop:false,
    references:[{scope:'REFERENCE_ONLY',file:'assets/recorded-references/a.wav',sha256:'a'.repeat(64),identity:{},source:{},automaticLoop:false}]
  }));
  globalThis.fetch=async()=>new Response(good);
  assert.equal((await loadRecordedReferenceCatalog(new URL('http://localhost/'))).references.length,1);
  for(const mutation of [
    x=>x.scope='PRODUCT',
    x=>x.automaticLoop=true,
    x=>delete x.references[0].sha256,
    x=>x.references[0].automaticLoop=true
  ]) {
    const bad=JSON.parse(good.toString('utf8'));mutation(bad);
    globalThis.fetch=async()=>new Response(Buffer.from(JSON.stringify(bad)));
    await assert.rejects(()=>loadRecordedReferenceCatalog(new URL('http://localhost/')));
  }
});
