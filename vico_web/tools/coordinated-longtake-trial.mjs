/**
 * HC-C1 one fixed synthetic long-take trial against the actual git-bound
 * Hellcat bank. Not a real-recording fit or OEM similarity evaluation.
 * Outputs are written ONLY to a new caller-provided diagnostic directory.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {BankRenderer,PEAK_CONTRACT} from '../src/core.mjs';
import {CoordinatedLongTakeVoice} from '../src/coordinated-longtake.mjs';
import {coordinatedSyntheticFixture} from '../test/coordinated-fixture.mjs';
import {diskBank,f32Bytes} from './render.mjs';

export const TRIAL_SCHEMA = 'vico.hc_c1.synthetic_trial.v1';
const SCENARIOS=Object.freeze([
 {id:'low_steady',seconds:4,rpm:[975,975],load:[.32,.32]},
 {id:'high_steady',seconds:4,rpm:[1500,1500],load:[.8,.8]},
 {id:'ramp_up',seconds:4,rpm:[975,1500],load:[.32,.8]},
 {id:'ramp_down',seconds:4,rpm:[1500,975],load:[.8,.32]},
]);
const hash=b=>createHash('sha256').update(b).digest('hex');

function sampleBank(bank,spec,recorded){
 const n=Math.round(spec.seconds*bank.sampleRate),out=new Float32Array(n);
 const r=new BankRenderer(bank,'NORMAL_SEAM_ENVELOPE_V1');
 const voice=recorded?new CoordinatedLongTakeVoice(coordinatedSyntheticFixture(),{alreadyVerified:true}):null;
 for(let frame=0;frame<n;frame+=960){
  const size=Math.min(n-frame,960),p=frame/n;
  const rpm=spec.rpm[0]+(spec.rpm[1]-spec.rpm[0])*p;
  const load=spec.load[0]+(spec.load[1]-spec.load[0])*p;
  const state={timeS:frame/bank.sampleRate,rpm,load,shiftGain:1,
    muted:false,afterfireTrigger:false,shiftTrigger:false};
  r.setState(state);
  if(voice)voice.setControl(rpm,load);
  for(let i=0;i<size;i++)out[frame+i]=r.next(voice?.next());
 }
 const stats=r.stats();
 if(stats.frames!==n||stats.nonfinite!==0||stats.hardClips!==0||
    stats.aboveContract!==0||stats.preClipPeak>PEAK_CONTRACT)throw new Error('Actual mixed PCM safety rejection');
 const voiceStats=voice?.stats()??null;
 if(voiceStats && (voiceStats.renderedFrames!==n||voiceStats.nonfinite!==0||
    voiceStats.preMixPeak>.55))throw new Error('Experimental source safety rejection');
 return {pcm:out,stats,voiceStats};
}
function firstDifferencePeak(pcm){
 let peak=0;
 for(let i=1;i<pcm.length;i++)peak=Math.max(peak,Math.abs(pcm[i]-pcm[i-1]));
 return peak;
}
function lagCorrelation(pcm,lag){
 if(!Number.isSafeInteger(lag)||lag<=0||lag>=pcm.length)return null;
 let dot=0,left=0,right=0;
 for(let i=0;i<pcm.length-lag;i++){const a=pcm[i],b=pcm[i+lag];dot+=a*b;left+=a*a;right+=b*b;}
 return left>0&&right>0?dot/Math.sqrt(left*right):null;
}
function envelopeDb(pcm,window=4800){
 const result=[];
 for(let start=0;start+window<=pcm.length;start+=window){
  let e=0;
  for(let i=0;i<window;i++)e+=pcm[start+i]*pcm[start+i];
  result.push(10*Math.log10(Math.max(e/window,1e-20)));
 }
 return result;
}

export async function runCoordinatedSyntheticTrial({dist,output}){
 if(!dist||!output)throw new Error('Explicit dist and NEW diagnostic output required');
 const root=path.resolve(output);
 await fs.mkdir(root); // never overwrite prior evidence
 const {bank,identity,testOnly}=await diskBank(path.resolve(dist),'hellcat_v6');
 if(testOnly||bank.sampleRate!==48000||bank.vehicleKey!=='hellcat_v6')throw new Error('Actual Hellcat bank identity required');
 const receipt={schema:TRIAL_SCHEMA,bankIdentity:identity,testOnly:false,
    recordedSource:'PROGRAMMATIC_SYNTHETIC_FIXTURE_ONLY_NOT_GDC',
    referenceAlignment:'NOT_EVALUATED',productPromotion:false,
    trials:[],gate:'NUMERIC_ONLY',failures:[],skipped:[]};
 for(const s of SCENARIOS){
  const baseline=sampleBank(bank,s,false),candidate=sampleBank(bank,s,true);
  const originalBytes=f32Bytes(baseline.pcm),synthBytes=f32Bytes(candidate.pcm);
  await fs.writeFile(path.join(root,s.id+'-actual-bank.f32le'),originalBytes,{flag:'wx'});
  await fs.writeFile(path.join(root,s.id+'-optin-synthetic.f32le'),synthBytes,{flag:'wx'});
  // Re-run the same requested control path before trusting the numeric receipt.
  // This is a deterministic engineering guard, NOT a Hellcat timbre judgement.
  const repeat=sampleBank(bank,s,true),repeatBytes=f32Bytes(repeat.pcm);
  if(hash(repeatBytes)!==hash(synthBytes)||repeat.stats.frames!==candidate.stats.frames)
    throw new Error('HC-C1 controlled synthetic output was not deterministic');
  const oldDb=envelopeDb(baseline.pcm),newDb=envelopeDb(candidate.pcm);
  receipt.trials.push({id:s.id,frames:baseline.pcm.length,rate:bank.sampleRate,
    input:{rpm:s.rpm,load:s.load},actualBank:{sha256:hash(originalBytes),stats:baseline.stats},
    syntheticOptIn:{sha256:hash(synthBytes),stats:candidate.stats,voice:candidate.voiceStats},
    relative100msDb:{minimum:Math.min(...newDb.map((v,i)=>v-oldDb[i])),
      maximum:Math.max(...newDb.map((v,i)=>v-oldDb[i]))},
    controlledReplay:{sameInputSha256:hash(repeatBytes),deterministic:hash(repeatBytes)===hash(synthBytes)},
    boundedContinuity:{actualMaxAdjacentJump:firstDifferencePeak(baseline.pcm),
      syntheticMaxAdjacentJump:firstDifferencePeak(candidate.pcm),
      original553846msCorrelation:lagCorrelation(baseline.pcm,Math.round(.553846*bank.sampleRate)),
      experimental553846msCorrelation:lagCorrelation(candidate.pcm,Math.round(.553846*bank.sampleRate))},
    acousticQualification:'NOT_EVALUATED_DIFFERENT_SYNTHETIC_VOICE'});
 }
 if(receipt.trials.length!==4||receipt.trials.some(x=>x.frames!==192000||!x.controlledReplay.deterministic||
    !Number.isFinite(x.boundedContinuity.actualMaxAdjacentJump)||
    !Number.isFinite(x.boundedContinuity.syntheticMaxAdjacentJump)))
  throw new Error('Incomplete preregistered trial');
 const json=JSON.stringify(receipt,null,2)+'\n';
 await fs.writeFile(path.join(root,'receipt.json'),json,{flag:'wx'});
 return receipt;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args=process.argv.slice(2),get=flag=>args.includes(flag)?args[args.indexOf(flag)+1]:null;
 if(args.includes('--help'))console.log('node vico_web/tools/coordinated-longtake-trial.mjs --dist VERIFIED_DIST --out NEW_DIAGNOSTIC_DIR');
 else runCoordinatedSyntheticTrial({dist:get('--dist'),output:get('--out')}).then(r=>
  console.log(JSON.stringify({gate:r.gate,trials:r.trials.length,missingRealAlignedReference:true})))
  .catch(e=>{console.error(e.stack||e.message);process.exitCode=1});
}
