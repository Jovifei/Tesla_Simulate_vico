import test from 'node:test';
import assert from 'node:assert/strict';
import {comparePcm} from '../tools/parity_metrics.mjs';
test('100ms comparison visits every sample-stride window including final window',()=>{
 const x=new Float32Array(30).fill(.1),y=x.slice();y[15]=.4;
 const r=comparePcm(x,y,100);
 assert.equal(r.rollingWindows,21);
 assert.ok(r.failedRollingWindows>0);
});
test('absolute envelope band power resolves 2Hz modulation',()=>{
 const x=Float32Array.from({length:12000},(_,i)=>.2*(1+.5*Math.cos(2*Math.PI*2*i/1000)));
 const r=comparePcm(x,x,1000);
 assert.equal(r.maxAbsError,0);
 assert.ok(r.envelopePower.reference>0.001);
 assert.equal(r.envelopePower.delta,0);
});
