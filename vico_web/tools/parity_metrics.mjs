/** Digital comparison only. Window starts advance by exactly one PCM sample. */
export function comparePcm(x,y,rate){
 if(x.length!==y.length)throw new Error('PCM length mismatch');
 const n=Math.round(rate*.1);let a=0,b=0,maxAbsError=0,se=0,maxDb=0,failed=0,count=0;
 for(let i=0;i<x.length;i++){
  if(!Number.isFinite(x[i])||!Number.isFinite(y[i]))throw new Error('Nonfinite PCM');
  const e=x[i]-y[i];maxAbsError=Math.max(maxAbsError,Math.abs(e));se+=e*e;a+=x[i]*x[i];b+=y[i]*y[i];
  if(i>=n){a-=x[i-n]*x[i-n];b-=y[i-n]*y[i-n];}
  if(i>=n-1){const d=a<=0?(b<=0?0:Infinity):10*Math.log10(Math.max(0,b)/a);maxDb=Math.max(maxDb,Math.abs(d));if(Math.abs(d)>.5)failed++;count++;}
 }
 // Absolute (not normalized) RMS-envelope periodogram; 10ms bins,
 // mean removed, rectangular full-record DFT, integrated positive-frequency power.
 const power=pcm=>{const hop=Math.round(rate*.01),env=[];for(let i=0;i+hop<=pcm.length;i+=hop){let s=0;for(let j=0;j<hop;j++)s+=pcm[i+j]**2;env.push(Math.sqrt(s/hop));}const N=env.length,mean=env.reduce((s,v)=>s+v,0)/N;let total=0;for(let k=Math.ceil(1.6*N/100);k<=Math.floor(2.1*N/100);k++){let re=0,im=0;for(let j=0;j<N;j++){const q=2*Math.PI*k*j/N;re+=(env[j]-mean)*Math.cos(q);im-=(env[j]-mean)*Math.sin(q);}total+=2*(re*re+im*im)/(N*N);}return total;};
 const p=power(x),q=power(y);
 return {maxAbsError,rmsError:Math.sqrt(se/x.length),rollingWindows:count,failedRollingWindows:failed,maxRolling100msAbsDb:maxDb,envelopePower:{bandHz:[1.6,2.1],method:'10ms RMS; mean removed; full-record rectangular DFT; absolute integrated positive-frequency power',reference:p,web:q,delta:q-p}};
}
