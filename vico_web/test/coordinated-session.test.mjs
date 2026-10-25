import test from 'node:test';
import assert from 'node:assert/strict';
import {verifyCoordinatedCandidate,stageCoordinatedCandidate} from '../src/session.mjs';
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

test('session stages owned F32LE bytes and region descriptors after full SHA verification',async()=>{
 const original=coordinatedSyntheticFixture(),staged=await stageCoordinatedCandidate(original);
 assert.notEqual(staged.samples,original.samples);
 assert.notEqual(staged.regions,original.regions);
 assert.notEqual(staged.regions[0],original.regions[0]);
 assert.equal(staged.pcmSha256,original.pcmSha256);
 original.samples[1000]=0;
 original.regions[0].referenceLoad=.99;
 assert.notEqual(staged.samples[1000],original.samples[1000]);
 assert.equal(staged.regions[0].referenceLoad,.3);
 assert.equal(await verifyCoordinatedCandidate(staged),true);
 staged.samples[1200]=Math.fround(staged.samples[1200]+.2);
 await assert.rejects(verifyCoordinatedCandidate(staged),/identity mismatch/);
});

test('staging rejects same-length tampered and mislabeled sources before audio transfer',async()=>{
 const c=coordinatedSyntheticFixture();
 c.samples[4000]=.3;
 await assert.rejects(stageCoordinatedCandidate(c),/PCM identity mismatch/);
 const fresh=coordinatedSyntheticFixture();
 await assert.rejects(stageCoordinatedCandidate({...fresh,evidence:{...fresh.evidence,licenseGate:'UNVERIFIED'}}));
});
