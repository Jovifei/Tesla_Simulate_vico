import fs from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';import {SOURCE_SHA} from '../src/core.mjs';
export const sha=b=>createHash('sha256').update(b).digest('hex');
export async function validateDynamicReference(reference,trajectory){
 const r=JSON.parse(await fs.readFile(path.join(reference,'receipt.json')));
 if(r.schema!=='vico.web.kotlin-dynamic.v2'||r.sourceCommit!==SOURCE_SHA)throw Error('Dynamic source identity mismatch');
 const check=async(file,hash)=>{if(!/^[a-f0-9]{64}$/.test(hash)||sha(await fs.readFile(file))!==hash)throw Error('Dynamic hash identity mismatch: '+file);};
 await check(r.staticReceipt,r.staticReceiptSha256);const s=JSON.parse(await fs.readFile(r.staticReceipt));if(s.sourceCommit!==SOURCE_SHA)throw Error('Static source identity mismatch');
 if(!Object.keys(r.compilerSources||{}).length||!Object.keys(r.artifacts||{}).length||!Object.keys(r.trajectorySha256||{}).length)throw Error('Missing dynamic identity');
 for(const [file,hash] of Object.entries(r.compilerSources)){if(s.compiler_inputs[path.basename(file)]!==hash)throw Error('Pinned Kotlin source identity mismatch');await check(file,hash);}
 for(const [name,hash] of Object.entries(r.trajectorySha256)){if(path.basename(name)!==name)throw Error('Trajectory identity path');await check(path.join(trajectory,name),hash);}
 for(const [name,hash] of Object.entries(r.artifacts)){if(path.basename(name)!==name)throw Error('Artifact identity path');await check(path.join(reference,name),hash);}
 return r;
}
