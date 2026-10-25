import test from 'node:test';
import assert from 'node:assert/strict';
import {verifyCoordinatedCandidate} from '../src/session.mjs';
import {coordinatedSyntheticFixture} from './coordinated-fixture.mjs';
import {fixtureBank} from './fixtures.mjs';

test('complete F32LE SHA binds aligned continuous voice before UI/worklet transfer',async()=>{
 const c=coordinatedSyntheticFixture();
 assert.equal(await verifyCoordinatedCandidate(c),true);
 c.samples[1000]=Math.fround(c.samples[1000]+.003);
 await assert.rejects(verifyCoordinatedCandidate(c),/PCM identity mismatch/);
});

test('wrong evidence/domain never treats source SHA as a valid product permission',async()=>{
 const c=coordinatedSyntheticFixture();
 for(const invalid of [
  {...c,evidence:{...c.evidence,licenseGate:'UNKNOWN'}},
  {...c,evidence:{...c.evidence,sourceClass:'LICENSED_RECORDED_TAKE'}},
  {...c,evidence:{...c.evidence,phaseState:'UNKNOWN'}},
  {...c,evidence:{...c.evidence,captureState:'NO_SYNCHRONIZED_RPM'}},
  {...c,vehicleKey:'gtr_r35'},
  {...c,regions:[c.regions[0],{...c.regions[1],referenceRpm:900}]},
 ]){
  await assert.rejects(verifyCoordinatedCandidate(invalid));
 }
});
