import {LiveEngine,StreamingResampler} from './core.mjs';
class VicoProcessor extends AudioWorkletProcessor {
  constructor(){super();this.engine=null;this.owner=0;this.counter=0;this.failed=false;this.port.onmessage=({data:m})=>{
    try{
      if(m.type==='init'){
        if(this.engine)throw new Error('Audio processor already initialized');
        this.owner=m.owner;this.engine=new LiveEngine(m.bank,m.mode);this.resampler=new StreamingResampler(this.engine,sampleRate);this.port.postMessage({type:'ready'});
      }else if(m.type==='stop'){this.engine?.command(m);}
      else if(m.owner===this.owner)this.engine?.command(m);
    }catch(e){this.failed=true;this.port.postMessage({type:'error',message:e.message});}
  };}
  process(_inputs,outputs){
    const channel=outputs[0]?.[0];if(!channel)return true;
    if(!this.engine||this.failed){channel.fill(0);return true;}
    try{
      for(let i=0;i<channel.length;i++)channel[i]=this.engine.stopped?0:this.resampler.next();
      this.counter+=channel.length;
      if(this.counter>=sampleRate/5){this.counter=0;this.port.postMessage({type:'stats',stats:this.engine.snapshot()});}
      return true;
    }catch(e){channel.fill(0);this.failed=true;this.port.postMessage({type:'error',message:e.message});return true;}
  }
}
registerProcessor('vico-bank',VicoProcessor);
