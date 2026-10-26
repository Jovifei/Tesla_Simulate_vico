export const RECORDED_REFERENCE_SCHEMA = 'vico.recorded.reference.v1';
const LICENSES = new Map([
  ['CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/'],
  ['CC0', 'https://creativecommons.org/publicdomain/zero/1.0/']
]);

const safeId = value => typeof value === 'string' && /^[a-z0-9][a-z0-9-]{2,63}$/.test(value);
const safePath = value => typeof value === 'string' && /^[a-z0-9][a-z0-9/.-]+\.wav$/.test(value) && !value.includes('..');

export function validateRecordedReference(reference) {
  if (!reference || reference.schema !== RECORDED_REFERENCE_SCHEMA || reference.scope !== 'REFERENCE_ONLY')
    throw new Error('Expected a REFERENCE_ONLY recorded reference');
  if (!safeId(reference.id) || !safePath(reference.file))
    throw new Error('Invalid recorded reference id or file');
  if (!Number.isSafeInteger(reference.sampleRate) || ![24000, 48000].includes(reference.sampleRate))
    throw new Error('Unsupported reference sample rate');
  if (![1, 2].includes(reference.channels) || !Number.isSafeInteger(reference.frames) || reference.frames < 1)
    throw new Error('Invalid reference format');
  if (reference.automaticLoop !== false)
    throw new Error('Recorded references must not auto-loop');

  const source = reference.source || {};
  if (!source.author?.trim() || !LICENSES.get(source.license) || source.licenseUrl !== LICENSES.get(source.license))
    throw new Error('Missing source author/license evidence');

  const identity = reference.identity || {};
  if (!identity.vehicle?.trim() || identity.state !== 'UNKNOWN' ||
      identity.synchronizedRpmLoad !== false || identity.OEMQualification !== false)
    throw new Error('Reference claims unverified vehicle state or qualification');

  return Object.freeze({scope: reference.scope, id: reference.id, file: reference.file,
    sampleRate: reference.sampleRate, channels: reference.channels, frames: reference.frames,
    vehicle: identity.vehicle, license: source.license});
}

export function segmentFrames(reference, startSeconds, endSeconds) {
  validateRecordedReference(reference);
  const duration = reference.frames / reference.sampleRate;
  if (!Number.isFinite(startSeconds) || !Number.isFinite(endSeconds) ||
      startSeconds < 0 || endSeconds > duration + Number.EPSILON || endSeconds <= startSeconds)
    throw new Error('Invalid reference segment');
  const startFrame = Math.round(startSeconds * reference.sampleRate);
  const endFrame = Math.min(reference.frames, Math.round(endSeconds * reference.sampleRate));
  if (startFrame < 0 || endFrame > reference.frames || endFrame <= startFrame)
    throw new Error('Reference segment outside source');
  return {startFrame, endFrame};
}

const digestBytes = async bytes => {
  if (!globalThis.crypto?.subtle) throw new Error('Browser SHA-256 unavailable');
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
};

export class RecordedReferencePlayer {
  constructor(reference, fetchImpl=globalThis.fetch, base=new URL('../', import.meta.url), documentImpl=globalThis.document) {
    validateRecordedReference(reference);
    if (!/^[0-9a-f]{64}$/.test(reference.sha256||'')) throw new Error('Reference SHA-256 required');
    this.reference=reference;this.fetchImpl=fetchImpl;this.base=base;this.documentImpl=documentImpl;this.verified=false;this.url=null;
  }
  async prepare({signal}={}) {
    if (this.verified) return;
    const response=await this.fetchImpl.call(globalThis,new URL(this.reference.file,this.base),{signal,credentials:'omit',redirect:'error'});
    if (!response.ok) throw new Error(`Reference fetch failed: ${response.status}`);
    const limit=this.reference.bytes??32*1024*1024;
    if(!Number.isSafeInteger(limit)||limit<1||limit>32*1024*1024||Number(response.headers.get('content-length'))>limit)
      throw new Error('Reference length limit');
    const reader=response.body.getReader(),parts=[];let length=0;
    while(true){
      const {value,done}=await reader.read();if(done)break;
      length+=value.byteLength;
      if(length>limit){await reader.cancel();throw new Error('Reference length limit');}
      parts.push(value);
    }
    if(this.reference.bytes!==undefined&&length!==limit)throw new Error('Reference length mismatch');
    const packed=new Uint8Array(length);let at=0;
    for(const part of parts){packed.set(part,at);at+=part.length;}
    const bytes=packed.buffer;
    if (await digestBytes(bytes) !== this.reference.sha256) throw new Error('Reference SHA-256 mismatch');
    this.bytes=bytes;
    this.verified=true;
  }
  async play(options) {
    await this.prepare(options);
    return {bytes:this.bytes,verified:true,loop:false};
  }
}

/** Owns real PCM auditions; every asynchronous boundary must retain this owner. */
export class ReferenceAuditionSession {
  constructor({base=new URL('../',import.meta.url),fetchImpl=globalThis.fetch,
    createContext=()=>new (globalThis.AudioContext||globalThis.webkitAudioContext)(),onChange=()=>{}}={}){
    this.base=base;this.fetchImpl=fetchImpl;this.createContext=createContext;this.onChange=onChange;
    this.volume=.2;this.run=null;
  }
  report(run,stage,detail=''){
    if(this.run===run)this.onChange({id:run.id,stage,detail,startSeconds:run.start,endSeconds:run.end});
  }
  release(run){
    if(!run||run.closed)return;run.closed=true;run.abort.abort();
    if(run.source){run.source.onended=null;try{run.source.stop();}catch{}run.source.disconnect();}
    run.envelope?.disconnect();run.level?.disconnect();
    try{Promise.resolve(run.context?.close()).catch(()=>{});}catch{}
  }
  stop(){
    const run=this.run;if(!run)return;
    this.report(run,'stopped');this.run=null;this.release(run);
  }
  setVolume(value){
    if(!Number.isFinite(value))return;
    this.volume=Math.min(.7,Math.max(0,value));
    if(this.run?.level)this.run.level.gain.value=this.volume;
  }
  async play(reference,{startSeconds=0,endSeconds=reference.frames/reference.sampleRate}={}){
    this.stop();
    const range=segmentFrames(reference,startSeconds,endSeconds);
    const run={id:reference.id,start:range.startFrame/reference.sampleRate,end:range.endFrame/reference.sampleRate,
      abort:new AbortController(),closed:false};
    this.run=run;
    try{
      run.context=this.createContext();this.report(run,'loading');
      // resume is called synchronously from the user gesture, before any network await.
      await run.context.resume();if(this.run!==run)return false;
      const player=new RecordedReferencePlayer(reference,this.fetchImpl,this.base);
      const {bytes}=await player.play({signal:run.abort.signal});if(this.run!==run)return false;
      const buffer=await run.context.decodeAudioData(bytes.slice(0));if(this.run!==run)return false;
      const duration=reference.frames/reference.sampleRate;
      if(buffer.numberOfChannels!==reference.channels||Math.abs(buffer.duration-duration)>2/buffer.sampleRate)
        throw new Error('Decoded reference format/duration mismatch');
      const source=run.context.createBufferSource();run.source=source;source.buffer=buffer;source.loop=false;
      const envelope=run.context.createGain(),level=run.context.createGain();run.envelope=envelope;run.level=level;
      level.gain.value=this.volume;source.connect(envelope);envelope.connect(level);level.connect(run.context.destination);
      const now=run.context.currentTime,length=run.end-run.start,fade=Math.min(.008,length/2);
      envelope.gain.setValueAtTime(0,now);envelope.gain.linearRampToValueAtTime(1,now+fade);
      envelope.gain.setValueAtTime(1,now+length-fade);envelope.gain.linearRampToValueAtTime(0,now+length);
      source.onended=()=>{if(this.run!==run)return;this.report(run,'ended');this.run=null;this.release(run);};
      source.start(now,run.start,length);this.report(run,'playing');return true;
    }catch(error){
      if(this.run!==run)return false;
      this.report(run,'error',error.message);this.run=null;this.release(run);throw error;
    }
  }
}
