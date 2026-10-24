import test from 'node:test';
import assert from 'node:assert/strict';
import {readMotionSample, motionAxisText, createMotionMonitor,
 MOTION_MAX_AGE_MS, MOTION_FIRST_SAMPLE_LIMIT_MS} from '../src/motion-monitor.mjs';

function fixture({secure=true, constructor=true, permission, pendingPermission}={}) {
  const handlers=new Map(), nodes=new Map(), intervals=new Map();
  let now=100, next=0, permissionCalls=0, gpsCalls=0, audioCalls=0;
  const record=(name,cb)=>{if(!handlers.has(name))handlers.set(name,new Set()); handlers.get(name).add(cb);};
  const cancel=(name,cb)=>handlers.get(name)?.delete(cb);
  const el=id=>{
    if(!nodes.has(id)) nodes.set(id,{id,disabled:false,textContent:'',listeners:new Map(),
      addEventListener(name,cb){if(!this.listeners.has(name))this.listeners.set(name,[]);this.listeners.get(name).push(cb);},
      async click(){for(const cb of this.listeners.get('click')||[])await cb();}});
    return nodes.get(id);
  };
  const doc={hidden:false,getElementById:el,addEventListener:record};
  const win={isSecureContext:secure,performance:{now:()=>now},
    addEventListener:record,removeEventListener:cancel,
    setInterval(fn){const id=++next;intervals.set(id,fn);return id;},
    clearInterval(id){intervals.delete(id);},
    navigator:{geolocation:{watchPosition(){gpsCalls++}}},
    AudioContext:class {constructor(){audioCalls++}}
  };
  if(constructor){
    win.DeviceMotionEvent={};
    if(permission!==undefined||pendingPermission){win.DeviceMotionEvent.requestPermission=()=>{permissionCalls++;return pendingPermission||Promise.resolve(permission);};}
  }
  const monitor=createMotionMonitor({win,doc});
  const emit=async(name,value)=>{for(const cb of [...(handlers.get(name)||[])])await cb(value)};
  const advance=ms=>{now+=ms;for(const fn of [...intervals.values()])fn();};
  return {monitor,win,doc,el,emit,advance,
    subscriptions:()=>handlers.get('devicemotion')?.size||0, pendingTimers:()=>intervals.size,
    getCalls:()=>({permissionCalls,gpsCalls,audioCalls})};
}

test('pure decoder distinguishes gravity-compensated, gravity-inclusive and null axes',()=>{
 assert.deepEqual(readMotionSample({acceleration:{x:0,y:-0.35,z:5}}),{x:0,y:-0.35,z:5,includesGravity:false});
 assert.deepEqual(readMotionSample({acceleration:{x:0,y:null,z:1},accelerationIncludingGravity:{x:0,y:9.8,z:0}}),{x:0,y:9.8,z:0,includesGravity:true});
 assert.equal(readMotionSample({acceleration:{x:0,y:NaN,z:1}}),null);
 assert.equal(readMotionSample({}),null);
 assert.equal(motionAxisText(-0), '0.00');
 assert.equal(motionAxisText(-0.106), '-0.11');
 assert.equal(motionAxisText(Infinity), '—');
});

test('sensor is opt-in, never creates AudioContext or requests geolocation; stop releases it',async()=>{
 const f=fixture({permission:'granted'});
 assert.equal(f.subscriptions(),0);assert.equal(f.pendingTimers(),0);
 assert.equal(f.el('motion-x').textContent,'—');
 await f.el('motion-start').click();
 assert.equal(f.getCalls().permissionCalls,1);
 assert.equal(f.subscriptions(),1);assert.equal(f.pendingTimers(),1);
 await f.emit('devicemotion',{acceleration:{x:1.25,y:-2.5,z:0}});
 assert.equal(f.el('motion-x').textContent,'1.25');
 assert.equal(f.el('motion-y').textContent,'-2.50');
 assert.match(f.el('motion-kind').textContent,/去除重力/);
 assert.equal(f.getCalls().audioCalls,0);assert.equal(f.getCalls().gpsCalls,0);
 await f.el('motion-stop').click();
 assert.equal(f.subscriptions(),0);assert.equal(f.pendingTimers(),0);
 assert.equal(f.el('motion-x').textContent,'—');
});

test('missing or denied permission fails closed with unknown readings',async()=>{
 for(const cfg of [{secure:false},{constructor:false},{permission:'denied'}]){
  const f=fixture(cfg);await f.el('motion-start').click();
  assert.equal(f.subscriptions(),0);assert.equal(f.el('motion-x').textContent,'—');
  assert.equal(f.el('motion-start').disabled,false);
  assert.equal(f.el('motion-stop').disabled,true);
 }
});

test('fallback with gravity is honestly labeled; invalid report immediately blanks values',async()=>{
 const f=fixture();await f.el('motion-start').click();
 await f.emit('devicemotion',{acceleration:{x:null,y:null,z:null},accelerationIncludingGravity:{x:0,y:9.806,z:0}});
 assert.equal(f.el('motion-y').textContent,'9.81');assert.match(f.el('motion-kind').textContent,/含重力/);
 await f.emit('devicemotion',{acceleration:{x:null,y:null,z:null}});
 assert.equal(f.el('motion-y').textContent,'—');
});

test('stale values clear; no sensor data eventually stops the listener',async()=>{
 const f=fixture();await f.el('motion-start').click();
 await f.emit('devicemotion',{acceleration:{x:5,y:0,z:0}});
 f.advance(MOTION_MAX_AGE_MS+1);
 assert.equal(f.el('motion-x').textContent,'—');assert.match(f.el('motion-status').textContent,/过期/);
 f.advance(MOTION_FIRST_SAMPLE_LIMIT_MS+1);
 assert.equal(f.subscriptions(),0);assert.match(f.el('motion-status').textContent,/未收到有效/);
});

test('late consent grant after stop cannot resurrect listener',async()=>{
 let grant;
 const f=fixture({pendingPermission:new Promise(resolve=>{grant=resolve;})});
 const pending=f.el('motion-start').click();
 assert.equal(f.el('motion-start').disabled,true);
 f.monitor.stop('用户停止');
 grant('granted');await pending;
 assert.equal(f.subscriptions(),0);assert.equal(f.el('motion-x').textContent,'—');
});

test('mode, stop, settings, hash, visibility and pagehide close sensor without touching sound',async()=>{
 for(const trigger of ['mode-gps','mode-manual','mode-demo','stop','back-garage','settings-toggle','hashchange','visibilitychange','pagehide']){
  const f=fixture();await f.el('motion-start').click();
  await f.emit('devicemotion',{acceleration:{x:1,y:2,z:3}});
  if(trigger==='visibilitychange'){f.doc.hidden=true;await f.emit(trigger)}
  else if(['pagehide','hashchange'].includes(trigger))await f.emit(trigger);
  else await f.el(trigger).click();
  assert.equal(f.subscriptions(),0,trigger);
  assert.equal(f.el('motion-x').textContent,'—',trigger);
  assert.equal(f.getCalls().gpsCalls,0,trigger);
 }
});

test('appearance, cluster and display-style controls do not change observer ownership',async()=>{
 const f=fixture();await f.el('motion-start').click();
 for(const id of ['appearance-cyber','appearance-minimal','cluster-touring','cluster-digital','display-style'])await f.el(id).click();
 assert.equal(f.subscriptions(),1);
 assert.equal(f.el('motion-stop').disabled,false);
});
