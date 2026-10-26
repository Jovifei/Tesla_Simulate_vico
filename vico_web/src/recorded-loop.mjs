/** Natural-rate recording loop. Complementary weights cannot exceed source peaks.
 * No gain normalization, pitch extrapolation, state inference or source edits.
 */
export function createRecordedCycle(channels,sampleRate,{startFrame=0,endFrame=channels[0]?.length}={}){
  if(!Number.isInteger(sampleRate)||sampleRate<8000||sampleRate>192000)
    throw new Error('Invalid PCM sample rate');
  if(!Array.isArray(channels)||![1,2].includes(channels.length)||
    channels.some(c=>!(c instanceof Float32Array)||c.length!==channels[0].length))
    throw new Error('Expected mono or stereo Float32 PCM');
  const length=endFrame-startFrame;
  if(!Number.isSafeInteger(startFrame)||!Number.isSafeInteger(endFrame)||startFrame<0||
    endFrame>channels[0].length||length<3*sampleRate||length>30*sampleRate)
    throw new Error('Recorded region must span 3 to 30 seconds within source');
  const crossfadeFrames=Math.round(.12*sampleRate),periodFrames=length-crossfadeFrames;
  const output=channels.map(channel=>{
    const region=channel.subarray(startFrame,endFrame);
    if(region.some(x=>!Number.isFinite(x)||Math.abs(x)>=1))
      throw new Error('Nonfinite or clipped PCM refused');
    const cycle=new Float32Array(periodFrames);
    for(let i=0;i<crossfadeFrames;i++){
      const head=.5-.5*Math.cos(Math.PI*i/(crossfadeFrames-1));
      cycle[i]=(1-head)*region[periodFrames+i]+head*region[i];
    }
    cycle.set(region.subarray(crossfadeFrames,periodFrames),crossfadeFrames);
    return cycle;
  });
  return {channels:output,sampleRate,crossfadeFrames,periodFrames,periodSeconds:periodFrames/sampleRate};
}
