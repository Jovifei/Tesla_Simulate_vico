import fs from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';
import {diskBank,renderConstant,f32Bytes} from './render.mjs';import {SOURCE_SHA,PEAK_CONTRACT} from '../src/core.mjs';
const a=process.argv.slice(2),get=k=>a[a.indexOf(k)+1];if(a.includes('--help')){console.log('node qualify.mjs --dist DIST --reference KOTLIN_OUT --out NEW_DIR');process.exit(0);}for(const k of ['--dist','--reference','--out'])if(!a.includes(k))throw new Error(`${k} required`);
const dist=path.resolve(get('--dist')),reference=path.resolve(get('--reference')),out=path.resolve(get('--out')),ref=JSON.parse(await fs.readFile(path.join(reference,'receipt.json')));
if(ref.schema!=='vico.web.kotlin-reference.v1'||ref.sourceCommit!==SOURCE_SHA||ref.cases.length!==48)throw new Error('Invalid actual Kotlin reference identity/count');
await fs.mkdir(path.dirname(out),{recursive:true});await fs.mkdir(out);const results=[],banks=new Map(),sha=b=>createHash('sha256').update(b).digest('hex');
for(const c of ref.cases){
 if(!/^[a-z0-9_-]+\.f32le$/.test(c.file))throw new Error('Reference path rejected');
 if(!banks.has(c.vehicle))banks.set(c.vehicle,await diskBank(dist,c.vehicle));const loaded=banks.get(c.vehicle);if(loaded.testOnly)throw new Error('Synthetic fixture cannot qualify actual bank');
 for(const key of ['referenceManifestSha256','variantManifestSha256'])if(loaded.identity[key]!==ref.banks[c.vehicle][key])throw new Error('Reference/bank mismatch');
 const old=await fs.readFile(path.join(reference,c.file));if(sha(old)!==c.sha256)throw new Error('Reference PCM hash mismatch');
 const {pcm,stats}=renderConstant(loaded.bank,ref.mode,c.rpm,c.load,c.seconds),bytes=f32Bytes(pcm);if(old.length!==bytes.length)throw new Error('Reference frame count mismatch');
 let maxError=0,sumError=0,windowOld=0,windowNew=0,windows=0,failedWindows=0,maxDb=0;
 for(let i=0;i<pcm.length;i++){const x=old.readFloatLE(i*4),y=pcm[i];if(!Number.isFinite(x)||!Number.isFinite(y))throw new Error('Nonfinite comparison');const e=x-y;maxError=Math.max(maxError,Math.abs(e));sumError+=e*e;windowOld+=x*x;windowNew+=y*y;
  if((i+1)%Math.round(loaded.bank.sampleRate*.1)===0){const delta=windowOld===0?(windowNew===0?0:Infinity):10*Math.log10(windowNew/windowOld);windows++;if(Math.abs(delta)>.5)failedWindows++;maxDb=Math.max(maxDb,Math.abs(delta));windowOld=0;windowNew=0;}
 }
 const pass=maxError<=2e-6&&failedWindows===0&&stats.aboveContract===0&&stats.hardClips===0&&stats.nonfinite===0;
 await fs.writeFile(path.join(out,c.file),bytes,{flag:'wx'});results.push({id:c.id,pass,frames:pcm.length,byteEqual:old.equals(bytes),maxAbsError:maxError,rmsError:Math.sqrt(sumError/pcm.length),windows,failedWindows,max100msAbsDb:maxDb,referenceSha256:sha(old),webSha256:sha(bytes),stats});
 console.log(c.id,pass?'PASS':'FAIL',maxError,maxDb);
}
const report={schema:'vico.web.parity.v1',sourceCommit:SOURCE_SHA,mode:ref.mode,thresholds:{maxAbsError:2e-6,windowDb:.5,peak:PEAK_CONTRACT},caseCount:results.length,passed:results.filter(r=>r.pass).length,scope:'STATIC_KOTLIN_JS_DIGITAL_NOT_BROWSER_DEVICE_ACOUSTIC',results};await fs.writeFile(path.join(out,'qualification.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});if(report.passed!==48)process.exitCode=1;
