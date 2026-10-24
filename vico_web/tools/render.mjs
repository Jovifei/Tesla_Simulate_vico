import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';import {createHash} from 'node:crypto';
import {BankRenderer,decodeF32Wav,MODES,SOURCE_SHA} from '../src/core.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
export async function diskBank(dist,id){
 const catalog=JSON.parse(await fs.readFile(path.join(dist,'catalog.json'))),entry=catalog.vehicles.find(x=>x.id===id);if(!entry)throw new Error('Unknown vehicle');
 if(!/^banks\/[a-z0-9_]+\/bank\.json$/.test(entry.bankFile))throw new Error('Invalid bank path');
 const raw=await fs.readFile(path.join(dist,entry.bankFile));if(sha(raw)!==entry.bankSha256)throw new Error('Bank hash mismatch');const d=JSON.parse(raw),dir=path.join(dist,path.dirname(entry.bankFile));
 const read=async row=>{if(!/^asset-[0-9a-f]{64}\.wav$/.test(row.file))throw new Error('Invalid PCM path');const b=await fs.readFile(path.join(dir,row.file));if(b.length!==row.bytes||sha(b)!==row.sha256)throw new Error('PCM identity mismatch');const v=decodeF32Wav(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength));if(v.sampleRate!==d.sampleRate)throw new Error('PCM rate mismatch');return v.samples;};
 const loops=[];for(const l of d.loops)loops.push({rpm:l.rpm,load:l.load,samples:await read(l)});
 const shifts=[];for(const r of d.shifts)shifts.push(await read(r));
 return {bank:{vehicleKey:id,sampleRate:d.sampleRate,spec:d.spec,loops,afterfire:await read(d.afterfire),shifts},identity:{bankSha256:entry.bankSha256,normalIdentity:d.normalIdentity,referenceManifestSha256:d.referenceManifestSha256,variantManifestSha256:d.variantManifestSha256,sourceCommit:d.sourceCommit},testOnly:catalog.testOnly};
}
export function renderConstant(bank,mode,rpm,load,seconds=12){
 if(!Number.isFinite(seconds)||seconds<=0||seconds>30)throw new Error('Duration must be 0..30 seconds');
 const frames=Math.round(seconds*bank.sampleRate),r=new BankRenderer(bank,mode),s={timeS:0,rpm,load,shiftGain:1,muted:false,shiftTrigger:false,afterfireTrigger:false},pcm=new Float32Array(frames);
 for(let at=0;at<frames;at+=960)pcm.set(r.render(s,Math.min(960,frames-at)),at);
 return {pcm,stats:r.stats()};
}
export function f32Bytes(pcm){const b=Buffer.alloc(pcm.length*4);for(let i=0;i<pcm.length;i++)b.writeFloatLE(pcm[i],i*4);return b;}
async function main(){const a=process.argv.slice(2),get=k=>a[a.indexOf(k)+1];if(a.includes('--help')){console.log('node render.mjs --dist DIST --vehicle c63_w204_v6 --rpm 910 --load .32 --out NEW_DIR [--mode MODE] [--seconds 12]');return;}for(const k of ['--dist','--vehicle','--rpm','--load','--out'])if(!a.includes(k))throw new Error(`${k} required`);
 const mode=a.includes('--mode')?get('--mode'):MODES[2],rpm=Number(get('--rpm')),load=Number(get('--load')),seconds=a.includes('--seconds')?Number(get('--seconds')):12;
 const {bank,identity,testOnly}=await diskBank(path.resolve(get('--dist')),get('--vehicle')),result=renderConstant(bank,mode,rpm,load,seconds),out=path.resolve(get('--out'));await fs.mkdir(path.dirname(out),{recursive:true});await fs.mkdir(out);const bytes=f32Bytes(result.pcm);await fs.writeFile(path.join(out,'capture.f32le'),bytes,{flag:'wx'});const receipt={scope:'WEB_DIGITAL_COMPONENT_NOT_ACOUSTIC',sourceCommit:SOURCE_SHA,identity,testOnly,vehicle:bank.vehicleKey,mode,rpm,load,seconds,frames:result.pcm.length,sha256:sha(bytes),stats:result.stats};await fs.writeFile(path.join(out,'receipt.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(receipt));}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(e=>{console.error(e.message);process.exitCode=1;});
