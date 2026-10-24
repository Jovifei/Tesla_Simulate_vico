import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs/promises';import os from 'node:os';import path from 'node:path';import {createHash} from 'node:crypto';
import {validateDynamicReference} from '../tools/dynamic_identity.mjs';import {SOURCE_SHA} from '../src/core.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
test('dynamic identity rejects stale source, altered trajectory and altered Kotlin PCM',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'vico-identity-'));try{
 const source=path.join(root,'Core.kt'),stat=path.join(root,'static.json');await fs.writeFile(source,'actual Kotlin');const staticBytes=JSON.stringify({sourceCommit:SOURCE_SHA,compiler_inputs:{'Core.kt':sha('actual Kotlin')}});await fs.writeFile(stat,staticBytes);await fs.writeFile(path.join(root,'demo.csv'),'0,0,0,0');await fs.writeFile(path.join(root,'case.f32le'),'pcm');
 const receipt={schema:'vico.web.kotlin-dynamic.v2',sourceCommit:SOURCE_SHA,staticReceipt:stat,staticReceiptSha256:sha(staticBytes),compilerSources:{[source]:sha('actual Kotlin')},trajectorySha256:{'demo.csv':sha('0,0,0,0')},artifacts:{'case.f32le':sha('pcm')},banks:{}};
 await fs.writeFile(path.join(root,'receipt.json'),JSON.stringify(receipt));await validateDynamicReference(root,root);
 for(const [file,value] of [[stat,'tampered static receipt'],[source,'tampered Kotlin'],[path.join(root,'demo.csv'),'stale'],[path.join(root,'case.f32le'),'tampered']]){const old=await fs.readFile(file);await fs.writeFile(file,value);await assert.rejects(validateDynamicReference(root,root),/identity|hash/i);await fs.writeFile(file,old);}
 receipt.sourceCommit='stale';await fs.writeFile(path.join(root,'receipt.json'),JSON.stringify(receipt));await assert.rejects(validateDynamicReference(root,root),/identity/i);
 }finally{await fs.rm(root,{recursive:true});}
});
