import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {SOURCE_SHA,decodeF32Wav,validateSpec,PEAK_CONTRACT} from '../src/core.mjs';
import {validateRecordedReference} from '../src/recorded-reference.mjs';
export const WEB=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const VEHICLES=Object.freeze([
  ['c63_w204_v6','Mercedes-Benz C63 W204','V8'],['hellcat_v6','Dodge Challenger SRT Hellcat','V8'],
  ['ferrari_458','Ferrari 458 Italia','V8'],['lfa','Lexus LFA','V10'],['gtr_r35','Nissan GT-R R35','V6'],['supra_jza80','Toyota Supra JZA80','I6']
]);
const ASSETS='vico_app/Project/android/app/src/main/assets';
const SPEC=['idle_rpm','redline_rpm','gear_ratios','final_drive','wheel_radius_m','launch_rpm','shift_rpm','shift_attack_s','shift_hold_s','shift_recovery_s','shift_settle_s','shift_min_torque','shift_reengage_gain','minimum_shift_interval_s','downshift_ratio','speed_ceiling_kmh','afterfire_minimum_rpm'];
export const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const leaf=name=>{if(typeof name!=='string'||!/^[A-Za-z0-9_.-]+$/.test(name)||name==='.'||name==='..')throw new Error('Invalid source asset filename');return name;};
function git(repo,args){const r=spawnSync('git',['--no-replace-objects','-C',repo,...args],{maxBuffer:16*1024*1024});if(r.status!==0)throw new Error(`Git source unavailable: ${args.slice(0,2).join(' ')}\n${r.stderr}`);return r.stdout;}
function validateStartupPack(pack){
  if(!pack)return;
  const m=pack.manifest,s=m?.source,q=m?.qualification;
  if(m?.schema!=='vico.startup.pack.v1'||m.vehicleKey!=='hellcat_v6'||m.sampleRate!==48000||!Number.isSafeInteger(m.frames)||m.frames<1||m.frames>480000)throw new Error('Invalid startup pack');
  if(s?.license!=='CC BY-SA 4.0'||s.licenseUrl!=='https://creativecommons.org/licenses/by-sa/4.0/'||!s.author?.trim()||!s.url?.startsWith('https://')||!/^[0-9a-f]{64}$/.test(s.originalSHA256)||q?.OEMQualification!==false||q?.automaticTuningEligible!==false||q?.role!=='ONE_SHOT_STARTUP')throw new Error('Invalid startup provenance');
  if(!pack.attribution?.includes(s.author)||!pack.attribution.includes(s.url)||!pack.attribution.includes(s.licenseUrl))throw new Error('Missing startup attribution');
  if(!Buffer.isBuffer(pack.pcm)||pack.pcm.length!==m.bytes||sha(pack.pcm)!==m.sha256)throw new Error('Startup SHA-256/length mismatch');
  const wav=decodeF32Wav(pack.pcm.buffer.slice(pack.pcm.byteOffset,pack.pcm.byteOffset+pack.pcm.byteLength));
  if(wav.sampleRate!==m.sampleRate||wav.samples.length!==m.frames||wav.samples.some(x=>Math.abs(x)>PEAK_CONTRACT))throw new Error('Startup PCM contract');
}
export async function readStartupPack(web=WEB){
  const root=path.join(web,'assets/startup/hellcat');
  const manifest=JSON.parse(await fs.readFile(path.join(root,'manifest.json'),'utf8'));
  const pack={manifest,pcm:await fs.readFile(path.join(root,leaf(manifest.file))),attribution:await fs.readFile(path.join(root,'ATTRIBUTION.txt'),'utf8')};
  validateStartupPack(pack);return pack;
}
export const RECORDED_REFERENCE_CATALOG=[
  Object.freeze({schema:'vico.recorded.reference.v1',scope:'REFERENCE_ONLY',id:'hellcat-startup-public',
    title:'Hellcat startup public recording',file:'hellcat-startup-original.wav',sampleRate:48000,channels:1,frames:314306,
    source:Object.freeze({author:'Axepas12',title:'Launching sound Challenger',url:'https://commons.wikimedia.org/wiki/File:Launching_sound_Challenger.ogg',
      license:'CC BY-SA 4.0',licenseUrl:'https://creativecommons.org/licenses/by-sa/4.0/'}),
    identity:Object.freeze({vehicle:'Dodge Challenger Hellcat',state:'UNKNOWN',synchronizedRpmLoad:false,OEMQualification:false}),
    automaticLoop:false}),
  Object.freeze({schema:'vico.recorded.reference.v1',scope:'REFERENCE_ONLY',id:'srt-version-unconfirmed',
    title:'Challenger SRT version unconfirmed',file:'srt-version-unconfirmed.wav',sampleRate:24000,channels:2,frames:5352000,
    source:Object.freeze({author:'JorisDJN',title:'Dodge Challenger SRT',url:'https://freesound.org/people/JorisDJN/sounds/760645/',
      license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/'}),
    identity:Object.freeze({vehicle:'Dodge Challenger SRT (version unconfirmed)',state:'UNKNOWN',synchronizedRpmLoad:false,OEMQualification:false}),
    automaticLoop:false})
  ,...[
    ['candidate-idle-low-35-55',35,55],['candidate-accel-63-69',63,69],
    ['candidate-accel-108-114',108,114],['candidate-accel-153-159',153,159],
    ['candidate-offload-160-170',160,170],['candidate-sustained-185-195',185,195]
  ].map(([id,start,end])=>Object.freeze({schema:'vico.recorded.reference.v1',scope:'REFERENCE_ONLY',id,
    title:`原录音 ${start}–${end} 秒`,file:`${id}.wav`,sampleRate:24000,channels:2,frames:(end-start)*24000,
    sourceSegment:Object.freeze({startSeconds:start,endSeconds:end,
      parentSha256:'a7fd478c1508308d0dce953763609dc5852819bf2f29a8d4c1972ca0d11450bd',stateConfidence:'UNVERIFIED'}),
    source:Object.freeze({author:'JorisDJN',title:'Dodge Challenger SRT',url:'https://freesound.org/people/JorisDJN/sounds/760645/',
      license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/'}),
    identity:Object.freeze({vehicle:'Dodge Challenger SRT (version unconfirmed)',state:'UNKNOWN',synchronizedRpmLoad:false,OEMQualification:false}),
    automaticLoop:false}))
];
const ACCEPTED_REFERENCE_HASHES=Object.freeze({
  'hellcat-startup-public':'2f25e56439294e8f847904282a31b36dc96f6a1fdeb4264e6f9a8b90aa9760f8',
  'srt-version-unconfirmed':'a7fd478c1508308d0dce953763609dc5852819bf2f29a8d4c1972ca0d11450bd',
  'candidate-idle-low-35-55':'2556075079affe33a7544c80a6fb866dc7771ee729c785752a43fe14fc00c2fb',
  'candidate-accel-63-69':'7391a4d02988753c2ec66f7f7bc73c4e3b970accd24c46501a01d8ee407699d1',
  'candidate-accel-108-114':'d24f31603df867aace829d9587f1e1fe6a712d12bb9da881416d98fe654ce28a',
  'candidate-accel-153-159':'d3de94681c96aac4db511028488bb11107d239ae29d2c597eca4d4edcfa60ce9',
  'candidate-offload-160-170':'e546e5899b89f3cc73f6fe3567ed15bf8b10b9f339b4406a4e75ed6dda8981ac',
  'candidate-sustained-185-195':'974a1200663dbc4aca89b9d95ec38eca69299c1d32f63f43f232ee8144c18bb3'
});
export async function readRecordedReferences(web=WEB){
  const out=[];
  for(const reference of RECORDED_REFERENCE_CATALOG){
    const bytes=await fs.readFile(path.join(web,'assets/recorded-references',reference.file));
    out.push({reference,pcm:bytes});
  }
  return out;
}
export async function buildSite({out,readBlob,web=WEB,webCommit='TEST_FIXTURE',testOnly=false,startupPack=null,recordedReferences=null}){
  validateStartupPack(startupPack);
  out=path.resolve(out);await fs.mkdir(path.dirname(out),{recursive:true});await fs.mkdir(out); // exclusive, never overwrite
  const catalog={schema:'vico.web.catalog.v1',sourceCommit:SOURCE_SHA,webCommit,testOnly,algorithm:'NORMAL_SEAM_ENVELOPE_V1',qualification:'PORT_REQUIRES_KOTLIN_BROWSER_DEVICE_VALIDATION',vehicles:[]};
  const write=async(relative,bytes)=>{const full=path.join(out,relative);await fs.mkdir(path.dirname(full),{recursive:true});await fs.writeFile(full,bytes,{flag:'wx'});};
  const references=recordedReferences??await readRecordedReferences(web);
  for(const item of references){
    const identity=validateRecordedReference(item.reference);
    if(!Buffer.isBuffer(item.pcm)||!item.pcm.length)throw new Error('Missing recorded reference PCM');
    item.sha256=sha(item.pcm);item.bytes=item.pcm.length;
    const accepted=RECORDED_REFERENCE_CATALOG.find(row=>row.id===identity.id);
    if(!accepted||JSON.stringify(accepted)!==JSON.stringify(item.reference))throw new Error('Recorded reference identity mismatch');
    if(item.sha256!==ACCEPTED_REFERENCE_HASHES[identity.id])throw new Error('Recorded reference SHA-256 differs from accepted source');
  }
  for(const [id,name,kind] of VEHICLES){
    const root=`${ASSETS}/s12_v10/${id}`, manifestBytes=await readBlob(`${root}/manifest.json`), m=JSON.parse(manifestBytes.toString('utf8'));
    if(m.vehicle_key!==id||!['vico.s12.soundbank.v1','vico.matlab.soundbank.v1'].includes(m.schema)||![48000,96000].includes(m.sample_rate_hz)||!Array.isArray(m.loops)||m.loops.length<1||m.loops.length>64||!Array.isArray(m.shift_events)||m.shift_events.length>16)throw new Error(`Invalid source bank: ${id}`);
    const spec=validateSpec(Object.fromEntries(SPEC.map(k=>[k,m[k]])));
    const replacements=new Map();let normalIdentity='legacy_unmodified',variantManifestSha256=null;
    if(id==='c63_w204_v6'){
      const overlay=`${ASSETS}/live_loop_variants/c63_low_rpm_preroll_v1`, propBytes=await readBlob(`${overlay}/manifest.properties`),props={};
      if(propBytes.length>8192||propBytes.includes(13))throw new Error('Invalid overlay encoding');
      for(const line of propBytes.toString('ascii').split('\n').filter(Boolean)){const at=line.indexOf('=');if(at<1||line.indexOf('=',at+1)>=0||Object.hasOwn(props,line.slice(0,at)))throw new Error('Invalid overlay properties');props[line.slice(0,at)]=line.slice(at+1);}
      if(props.schema!=='vico.live_loop_variant.v1'||props.variant_id!=='c63_low_rpm_preroll_v1'||props.vehicle_key!==id||props.loop_count!=='4'||Number(props.sample_rate_hz)!==m.sample_rate_hz||props.baseline_manifest_sha256!==sha(manifestBytes)||Number(props.fixed_vehicle_gain)!==m.fixed_vehicle_gain)throw new Error('C63 overlay identity mismatch');
      for(let i=0;i<4;i++){
        const get=k=>props[`loop.${i}.${k}`],file=leaf(get('file')),old=await readBlob(`${root}/${file}`),candidate=await readBlob(`${overlay}/${file}`),wav=decodeF32Wav(candidate.buffer.slice(candidate.byteOffset,candidate.byteOffset+candidate.byteLength));
        if(sha(old)!==get('baseline_wav_sha256')||sha(candidate)!==get('candidate_wav_sha256')||wav.sampleRate!==m.sample_rate_hz||wav.samples.length!==Number(get('samples'))||wav.samples.some(v=>Math.abs(v)>PEAK_CONTRACT+1e-7)||replacements.has(file))throw new Error('C63 overlay PCM validation failed');
        const row=m.loops.find(x=>x.file===file&&x.rpm===Number(get('rpm'))&&x.load===Number(get('load')));
        if(!row||![700,1400].includes(row.rpm)||![.32,.92].includes(row.load))throw new Error('C63 overlay mapping mismatch');
        replacements.set(file,candidate);
      }
      normalIdentity=props.variant_id;variantManifestSha256=sha(propBytes);
    }
    const seen=new Set();
    const asset=async row=>{
      const sourceName=leaf(row.file),bytes=replacements.get(sourceName)||await readBlob(`${root}/${sourceName}`);
      const wav=decodeF32Wav(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));if(wav.sampleRate!==m.sample_rate_hz)throw new Error('Asset rate differs from manifest');
      const digest=sha(bytes),file=`asset-${digest}.wav`;
      if(!seen.has(file)){await write(`banks/${id}/${file}`,bytes);seen.add(file);}
      return {file,sha256:digest,bytes:bytes.length,frames:wav.samples.length};
    };
    const loops=[];for(const row of m.loops)loops.push({rpm:row.rpm,load:row.load,...await asset(row)});
    const afterfire=await asset(m.afterfire),shifts=[];for(const row of m.shift_events)shifts.push(await asset(row));
    const d={schema:'vico.web.bank.v1',vehicleKey:id,name,sampleRate:m.sample_rate_hz,sourceCommit:SOURCE_SHA,normalIdentity,referenceManifestSha256:sha(manifestBytes),variantManifestSha256,fixedVehicleGain:m.fixed_vehicle_gain,gainPolicy:'already baked in original WAV; never applied again',spec,loops,afterfire,shifts};
    if(startupPack&&id==='hellcat_v6'){
      const s=startupPack.manifest,file=`asset-${s.sha256}.wav`;
      await write(`banks/${id}/${file}`,startupPack.pcm);
      d.startup={file,sha256:s.sha256,bytes:s.bytes,frames:s.frames,sampleRate:s.sampleRate,fadeInMs:s.fadeInMs,handoffMs:s.handoffMs,source:s.source,qualification:s.qualification,processing:s.processing,sourceCommit:webCommit};
    }
    const bytes=Buffer.from(JSON.stringify(d,null,2)+'\n'),bankFile=`banks/${id}/bank.json`;await write(bankFile,bytes);
    catalog.vehicles.push({id,name,kind,bankFile,bankSha256:sha(bytes),normalIdentity,idleRpm:spec.idle_rpm,redlineRpm:spec.redline_rpm,startupAvailable:!!d.startup});
  }
  for(const name of ['index.html','style.css','favicon.svg'])await write(name,await fs.readFile(path.join(web,name)));
  await fs.cp(path.join(web,'src'),path.join(out,'src'),{recursive:true,errorOnExist:true,force:false});
  const referenceCatalog={schema:'vico.recorded.reference.catalog.v1',scope:'REFERENCE_ONLY',automaticLoop:false,
    qualification:'SOURCE_TIMBRE_DIRECTION_ONLY_NOT_PRODUCT_OR_OEM',
    references:references.map(({reference,sha256,bytes})=>({...reference,file:`assets/recorded-references/${path.basename(reference.file)}`,sha256,bytes}))};
  for(const {reference,pcm} of references)await write(`assets/recorded-references/${reference.file}`,pcm);
  await write('recorded-references.json',Buffer.from(JSON.stringify(referenceCatalog,null,2)+'\n'));
  await write('audio-credits.txt',Buffer.from(startupPack?.attribution||'Vico original synthetic bank engine. No third-party startup recording is enabled in this build.\n'));
  await write('catalog.json',Buffer.from(JSON.stringify(catalog,null,2)+'\n'));
  const hashes={};async function walk(dir){for(const e of await fs.readdir(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())await walk(p);else hashes[path.relative(out,p).split(path.sep).join('/')]=sha(await fs.readFile(p));}}await walk(out);
  await write('build-manifest.json',Buffer.from(JSON.stringify({schema:'vico.web.build.v1',sourceCommit:SOURCE_SHA,webCommit,testOnly,files:hashes},null,2)+'\n'));
  return {out,vehicles:catalog.vehicles.length,files:Object.keys(hashes).length,testOnly};
}
async function main(){
  const args=process.argv.slice(2);if(args.includes('--help')){console.log('node vico_web/tools/build.mjs --out NEW_DIRECTORY [--repo REPOSITORY]');return;}
  const value=k=>args[args.indexOf(k)+1];if(!args.includes('--out'))throw new Error('--out NEW_DIRECTORY is required');
  const repo=path.resolve(args.includes('--repo')?value('--repo'):path.join(WEB,'..')),out=path.resolve(value('--out'));
  const repoReal=await fs.realpath(repo);await fs.mkdir(path.dirname(out),{recursive:true});const realOut=path.join(await fs.realpath(path.dirname(out)),path.basename(out));
  for(const protectedDir of [repoReal,path.join(repoReal,'vico_app'),path.join(repoReal,'.git')])if(realOut===protectedDir||protectedDir!==repoReal&&realOut.startsWith(protectedDir+path.sep))throw new Error('Protected output path');
  const webCommit=git(repo,['rev-parse','HEAD']).toString().trim();
  git(repo,['cat-file','-e',`${SOURCE_SHA}^{commit}`]);
  const result=await buildSite({out:realOut,webCommit,startupPack:await readStartupPack(WEB),readBlob:async p=>git(repo,['show',`${SOURCE_SHA}:${p}`])});console.log(JSON.stringify(result));
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(e=>{console.error(e.message);process.exitCode=1;});
