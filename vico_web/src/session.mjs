import {decodeF32Wav, MODES, PEAK_CONTRACT} from './core.mjs';
import {validateLongTake} from './coordinated-longtake.mjs';

export async function digest(bytes) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
}
/** Main-thread complete F32LE source SHA, before any real-time transfer.
 *  GDC restricted media is never downloaded or staged by this helper.
 */
export async function verifyCoordinatedCandidate(candidate) {
  validateLongTake(candidate);
  const a=candidate.samples;
  const bytes=new Uint8Array(a.buffer,a.byteOffset,a.byteLength);
  if(await digest(bytes)!==candidate.pcmSha256)throw new Error('Recorded PCM identity mismatch');
  return true;
}
/** Clone first, verify the exact bytes actually transferred, and keep source
 * approval metadata separate from the audio-thread object. Never mutate input. */
export async function stageCoordinatedCandidate(candidate) {
  validateLongTake(candidate);
  const staged={...candidate,samples:candidate.samples.slice(),
    regions:candidate.regions.map(r=>({...r})),evidence:{...candidate.evidence}};
  await verifyCoordinatedCandidate(staged);
  return staged;
}
export async function checkedFetch(url, expected, {signal, maxBytes=8*1024*1024}={}) {
  url=new URL(url,globalThis.location?.href || 'http://localhost');
  if (globalThis.location && url.origin!==location.origin) throw new Error('Cross-origin asset refused');
  const r=await fetch(url,{signal,credentials:'omit',cache:'no-cache',redirect:'error'});
  if (!r.ok) throw new Error(`资源加载失败 ${r.status}: ${url.pathname}`);
  const length=Number(r.headers.get('content-length'));
  if (length>maxBytes) throw new Error('Resource size bound');
  // Bounded streaming protects against a missing or dishonest Content-Length.
  const reader=r.body.getReader(), chunks=[]; let size=0;
  while(true) { const {value,done}=await reader.read(); if(done)break; size+=value.byteLength; if(size>maxBytes){await reader.cancel();throw new Error('Resource size bound');} chunks.push(value); }
  const bytes=new Uint8Array(size); let offset=0; for(const c of chunks){bytes.set(c,offset);offset+=c.length;}
  if(expected && (!/^[0-9a-f]{64}$/.test(expected)||await digest(bytes)!==expected)) throw new Error(`资源 SHA-256 不匹配: ${url.pathname}`);
  return bytes;
}
const decodeJSON = bytes => JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
export async function loadCatalog(base,signal) {
  const c=decodeJSON(await checkedFetch(new URL('catalog.json',base),null,{signal,maxBytes:65536}));
  if(c.schema!=='vico.web.catalog.v1'||!Array.isArray(c.vehicles)||c.vehicles.length!==6) throw new Error('Invalid six-vehicle catalog');
  return c;
}
export async function loadBank(entry,base,signal) {
  if(!/^banks\/[a-z0-9_]+\/bank\.json$/.test(entry.bankFile)) throw new Error('Invalid bank path');
  const bankURL=new URL(entry.bankFile,base), d=decodeJSON(await checkedFetch(bankURL,entry.bankSha256,{signal,maxBytes:65536}));
  if(d.schema!=='vico.web.bank.v1'||d.vehicleKey!==entry.id||d.loops.length>64||d.shifts.length>16) throw new Error('Bank identity mismatch');
  const start=d.startup??null;
  if(start&&(!Number.isSafeInteger(start.frames)||start.frames<1||start.frames>d.sampleRate*10||start.sampleRate!==d.sampleRate||!Number.isFinite(start.fadeInMs)||start.fadeInMs<0||start.fadeInMs>50||!Number.isFinite(start.handoffMs)||start.handoffMs<10||start.handoffMs>500||!start.source?.author?.trim()||!start.source?.url?.startsWith('https://')||start.source.license!=='CC BY-SA 4.0'||start.source.licenseUrl!=='https://creativecommons.org/licenses/by-sa/4.0/'||!/^[0-9a-f]{64}$/.test(start.source.originalSHA256)||start.qualification?.OEMQualification!==false))throw new Error('Invalid startup source contract');
  const rows=[...d.loops,d.afterfire,...d.shifts,...(start?[start]:[])];
  if(rows.some(r=>!/^asset-[0-9a-f]{64}\.wav$/.test(r.file)||!Number.isSafeInteger(r.bytes)||r.bytes<44||r.bytes>8*1024*1024)) throw new Error('Invalid asset descriptor');
  const decoded=new Array(rows.length); let next=0;
  await Promise.all(Array.from({length:Math.min(4,rows.length)},async()=>{
    while(next<rows.length) { const i=next++, row=rows[i], bytes=await checkedFetch(new URL(row.file,bankURL),row.sha256,{signal,maxBytes:row.bytes});
      if(bytes.length!==row.bytes)throw new Error('Asset length mismatch');
      const wav=decodeF32Wav(bytes.buffer); if(wav.sampleRate!==d.sampleRate) throw new Error('Bank sample rate mismatch');
      if(start&&i===rows.length-1&&(wav.samples.length!==start.frames||wav.samples.some(v=>Math.abs(v)>PEAK_CONTRACT)))throw new Error('Startup PCM contract');
      decoded[i]=wav.samples;
    }
  }));
  return {vehicleKey:d.vehicleKey,sampleRate:d.sampleRate,spec:d.spec,normalIdentity:d.normalIdentity,sourceCommit:d.sourceCommit,
    loops:d.loops.map((r,i)=>({rpm:r.rpm,load:r.load,samples:decoded[i]})),afterfire:decoded[d.loops.length],shifts:decoded.slice(d.loops.length+1,d.loops.length+1+d.shifts.length),
    startup:start?{samples:decoded.at(-1),sampleRate:start.sampleRate,sha256:start.sha256,fadeInMs:start.fadeInMs,handoffMs:start.handoffMs}:null,
    identity:{bankSha256:entry.bankSha256,referenceManifestSha256:d.referenceManifestSha256,normalIdentity:d.normalIdentity,sourceCommit:d.sourceCommit,startupSHA256:start?.sha256??null,startupSource:start?.source??null}};
}

/** Latest-owner-wins. A stopped/obsolete load can never resurrect playback. */
export class Owner {
  constructor(){this.id=0;this.abort=null;}
  next(){this.abort?.abort();this.abort=new AbortController();return {id:++this.id,signal:this.abort.signal};}
  owns(id){return this.id===id;}
  cancel(){this.abort?.abort();this.id++;}
}
export class AudioSession {
  constructor(base,onChange=()=>{}) { this.base=base; this.onChange=onChange;this.owner=new Owner();this.ctx=null;this.node=null;this.stage='idle';this.last=null;this.timer=null;this.volume=.2;this.pendingInput={source:'demo',scenario:'stop'}; }
  report(stage,detail=''){this.stage=stage;this.onChange({stage,detail,stats:this.last});}
  async start(entry,mode,input,{recordedCandidate=null}={}){
    if(!MODES.includes(mode))throw new Error('Unknown audio mode');
    const token=this.owner.next(); this.release(); this.last=null;this.pendingInput=input;
    let ctx;
    try {
      if(!globalThis.isSecureContext)throw new Error('请使用 HTTPS 或 localhost；不支持 file://');
      const Audio=globalThis.AudioContext||globalThis.webkitAudioContext;
      if(!Audio)throw new Error('浏览器不支持 Web Audio');
      ctx=new Audio({sampleRate:48000,latencyHint:'interactive'}); this.ctx=ctx;
      this.report('loading','正在校验你的声库');
      // Resume in the direct click call chain, before downloading any asset.
      await ctx.resume(); if(!ctx.audioWorklet)throw new Error('浏览器不支持 AudioWorklet');
      const [bank]=await Promise.all([loadBank(entry,this.base,token.signal),ctx.audioWorklet.addModule(new URL('src/worklet.mjs',this.base))]);
      if(!this.owner.owns(token.id)){await ctx.close();return;}
      let experimental=null;
      if(recordedCandidate){
        if(mode!=='NORMAL_SEAM_ENVELOPE_V1'||entry.id!=='hellcat_v6')
          throw new Error('Coordinated source requires explicit Hellcat normal mode');
        if(bank.sampleRate!==recordedCandidate.sampleRate)
          throw new Error('Coordinated source sample rate must match the internal renderer');
        experimental=await stageCoordinatedCandidate(recordedCandidate);
        if(!this.owner.owns(token.id)){await ctx.close();return;}
      }
      const node=new AudioWorkletNode(ctx,'vico-bank',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[1]});
      const volume=ctx.createGain();volume.gain.value=this.volume;node.connect(volume).connect(ctx.destination);this.node=node;this.volumeNode=volume;
      let readyResolve,readyReject;
      const ready=new Promise((resolve,reject)=>{readyResolve=resolve;readyReject=reject;});
      const timeout=setTimeout(()=>readyReject(new Error('音频处理器准备超时')),10000);
      const fail=message=>{if(!this.owner.owns(token.id))return;this.owner.cancel();this.release();this.report('error',message);};
      node.onprocessorerror=()=>fail('音频处理器异常，已停止');
      node.port.onmessage=({data})=>{
        if(!this.owner.owns(token.id))return;
        if(data.type==='ready')readyResolve();
        if(data.type==='error'){readyReject(new Error(data.message));fail(data.message);}
        if(data.type==='stats'){this.last={...data.stats,contextSampleRate:ctx.sampleRate,bankIdentity:bank.identity,qualification:'WEB_PORT_NOT_DEVICE_OR_ACOUSTIC_APPROVAL'};this.onChange({stage:this.stage,stats:this.last});}
      };
      const transfers=[...bank.loops.map(l=>l.samples.buffer),bank.afterfire.buffer,...bank.shifts.map(x=>x.buffer),...(bank.startup?[bank.startup.samples.buffer]:[])];
      if(experimental)transfers.push(experimental.samples.buffer);
      node.port.postMessage({type:'init',owner:token.id,bank,mode,input:this.freshInput(this.pendingInput),
        recordedCandidate:experimental,recordedVerified:Boolean(experimental)},transfers);
      try{await ready;}finally{clearTimeout(timeout);}
      if(!this.owner.owns(token.id)){await ctx.close();return;}
      node.port.postMessage({...this.freshInput(this.pendingInput),type:'input',owner:token.id});node.port.postMessage({type:'heartbeat',owner:token.id});
      this.timer=setInterval(()=>{if(this.owner.owns(token.id))node.port.postMessage({type:'heartbeat',owner:token.id});},250);
      ctx.onstatechange=()=>{if(this.owner.owns(token.id)&&this.stage==='running'&&ctx.state!=='running')fail('浏览器暂停了音频；请重新点击开始');};
      this.report('running',`${entry.name} · 声库已校验`);
    }catch(e){if(this.owner.owns(token.id)){this.owner.cancel();this.release();this.report('error',e.message);}else if(ctx&&ctx.state!=='closed')await ctx.close();}
  }
  freshInput(input){if(input.source!=='gps'||input.valid!==true)return input;if(!Number.isFinite(input.receivedAt))return {source:'gps',valid:false};return {...input,ageMs:input.ageMs+Math.max(0,performance.now()-input.receivedAt)};}
  setInput(input){this.pendingInput=input;if(this.node&&this.stage==='running')this.node.port.postMessage({...this.freshInput(input),type:'input',owner:this.owner.id});}
  setVolume(value){this.volume=Math.max(0,Math.min(.7,Number(value)||0));if(this.ctx&&this.volumeNode)this.volumeNode.gain.setTargetAtTime(this.volume,this.ctx.currentTime,.02);}
  async stop(immediate=false){
    this.owner.cancel();const id=this.owner.id,ctx=this.ctx,node=this.node;
    clearInterval(this.timer);this.timer=null;this.ctx=null;this.node=null;this.volumeNode=null;
    if(!ctx){this.report('idle');return;}
    this.report('stopping','正在停止');
    if(!immediate&&node){node.port.postMessage({type:'stop'});await new Promise(r=>setTimeout(r,450));}
    node?.disconnect();if(ctx.state!=='closed')await ctx.close();
    if(this.owner.owns(id))this.report('idle','声音已停止');
  }
  release(){clearInterval(this.timer);this.timer=null;this.node?.disconnect();this.node=null;const ctx=this.ctx;this.ctx=null;this.volumeNode=null;if(ctx&&ctx.state!=='closed')ctx.close().catch(()=>{});}
}
