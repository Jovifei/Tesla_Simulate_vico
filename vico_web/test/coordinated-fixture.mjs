import {createHash} from 'node:crypto';

/** Pure deterministic test take. NO field recording; test-only, never ship as product PCM. */
export function coordinatedSyntheticFixture(){
 const rate=48000, framesPerRegion=96000;
 const samples=new Float32Array(framesPerRegion*2);
 const control=[{rpm:960,load:.3,cycles:16,scale:.12},{rpm:1500,load:.8,cycles:25,scale:.2}];
 for(let c=0;c<2;c++){
  const cfg=control[c];
  for(let i=0;i<framesPerRegion;i++){
   const cycle=i*cfg.cycles/framesPerRegion;
   samples[c*framesPerRegion+i]=Math.fround(cfg.scale*Math.sin(2*Math.PI*cycle)
    +.022*Math.sin(2*Math.PI*cycle/Math.max(1,cfg.cycles))
    +.018*Math.sin(2*Math.PI*cycle*2));
  }
 }
 const digest=createHash('sha256').update(Buffer.from(samples.buffer)).digest('hex');
 return {schema:'vico.coordinated.longtake.v1',vehicleKey:'hellcat_v6',sampleRate:rate,
   takeId:'hellcat-synthetic-windows-v1',samples,pcmSha256:digest,
   evidence:{sourceClass:'SYNTHETIC_TEST_ONLY',licenseGate:'NOT_DISTRIBUTABLE_TEST',
     captureState:'SYNTHETIC_KNOWN_RPM_LOAD',phaseState:'SYNTHETIC_KNOWN_720',
     holdoutState:'SYNTHETIC_INDEPENDENT_GROUP'},
   regions:[
    {id:'low_rpm',startFrame:0,endFrame:framesPerRegion,cycles720:16,referenceRpm:960,referenceLoad:.3},
    {id:'high_rpm',startFrame:framesPerRegion,endFrame:2*framesPerRegion,cycles720:25,referenceRpm:1500,referenceLoad:.8}
   ]};
}
