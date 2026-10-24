import {createHash} from 'node:crypto';
export const spec={idle_rpm:700,redline_rpm:7200,gear_ratios:[4.38,2.86,1.92],final_drive:2.82,wheel_radius_m:.33,launch_rpm:2600,shift_rpm:7000,shift_attack_s:.018,shift_hold_s:.032,shift_recovery_s:.075,shift_settle_s:.055,shift_min_torque:.22,shift_reengage_gain:1.08,minimum_shift_interval_s:.35,downshift_ratio:.68,speed_ceiling_kmh:144,afterfire_minimum_rpm:2400};
export function state(rpm=910,load=.32){return {timeS:0,rpm,load,shiftGain:1,muted:false,afterfireTrigger:false,shiftTrigger:false};}
export function fixtureBank({constant=false,count=17280}={}){return {vehicleKey:'TEST_FIXTURE',sampleRate:48000,spec,loops:[700,1400,3000,7200].flatMap(rpm=>[.32,.92].map(load=>({rpm,load,samples:Float32Array.from({length:count},(_,i)=>constant?.2:.12*Math.sin(i*rpm/(120*48000)*2*Math.PI)*load+.03*Math.sin(i*.013))}))),afterfire:Float32Array.from([.3,-.2,.1]),shifts:[Float32Array.from([.2,-.1,.04])]};}
export function wav(samples,rate=48000){const b=Buffer.alloc(44+samples.length*4);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(3,20);b.writeUInt16LE(1,22);b.writeUInt32LE(rate,24);b.writeUInt32LE(rate*4,28);b.writeUInt16LE(4,32);b.writeUInt16LE(32,34);b.write('data',36);b.writeUInt32LE(samples.length*4,40);samples.forEach((x,i)=>b.writeFloatLE(x,44+i*4));return b;}
const sha=b=>createHash('sha256').update(b).digest('hex');
export function fixtureSources(){
 const files=new Map(),base='vico_app/Project/android/app/src/main/assets',ids=['c63_w204_v6','hellcat_v6','ferrari_458','lfa','gtr_r35','supra_jza80'];
 for(const id of ids){const bank=fixtureBank(),root=`${base}/s12_v10/${id}`,loops=bank.loops.map(l=>({rpm:l.rpm,load:l.load,file:`rpm_${String(l.rpm).padStart(4,'0')}_load_${l.load===.32?'32':'92'}.wav`}));
  const m={schema:'vico.s12.soundbank.v1',vehicle_key:id,sample_rate_hz:48000,fixed_vehicle_gain:1,...spec,loops,afterfire:{file:'after.wav'},shift_events:[{file:'shift.wav'}],source:'E:/private/path/must/not/ship'};
  files.set(`${root}/manifest.json`,Buffer.from(JSON.stringify(m)));loops.forEach((l,i)=>files.set(`${root}/${l.file}`,wav(bank.loops[i].samples)));files.set(`${root}/after.wav`,wav(bank.afterfire));files.set(`${root}/shift.wav`,wav(bank.shifts[0]));
  if(id==='c63_w204_v6'){
   const overlay=`${base}/live_loop_variants/c63_low_rpm_preroll_v1`;let props=`schema=vico.live_loop_variant.v1\nvariant_id=c63_low_rpm_preroll_v1\nvehicle_key=${id}\nsample_rate_hz=48000\nloop_count=4\nbaseline_manifest_sha256=${sha(files.get(`${root}/manifest.json`))}\nfixed_vehicle_gain=1\n`;
   loops.slice(0,4).forEach((l,i)=>{const b=files.get(`${root}/${l.file}`);files.set(`${overlay}/${l.file}`,b);for(const [k,v] of Object.entries({...l,samples:17280,baseline_wav_sha256:sha(b),candidate_wav_sha256:sha(b)}))props+=`loop.${i}.${k}=${v}\n`;});files.set(`${overlay}/manifest.properties`,Buffer.from(props));
  }
 }
 return files;
}
