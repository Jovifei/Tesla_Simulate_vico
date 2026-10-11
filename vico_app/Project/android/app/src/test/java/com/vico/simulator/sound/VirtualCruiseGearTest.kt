package com.vico.simulator.sound
import org.junit.Test
import org.junit.Assert.*
class VirtualCruiseGearTest {
 @Test fun cruiseAt70SettlesAboveFirstAndDoesNotHunt(){val p=VirtualCruiseGear(virtualDriveC63Spec());p.update(1.0,0.0,.08,true,true,true);var s=p.update(1.05,70.0,.08,true,false,false);var late=0;for(i in 2..400){s=p.update(1+i*.05,70.0,.08,true,false,false);if(i>100&&s.changed)late++};assertTrue(s.gear>1);assertEquals(0,late)}
 @Test fun recoveryAtSpeedSelectsGearWithoutEvents(){val p=VirtualCruiseGear(virtualDriveC63Spec());val s=p.update(1.0,70.0,.08,true,true,false);assertTrue(s.gear>1);assertFalse(s.changed)}
 @Test fun duplicateImuCannotAccumulateShiftDwell(){val p=VirtualCruiseGear(virtualDriveC63Spec());p.update(1.0,0.0,0.0,true,true,true);repeat(100){assertEquals(1,p.update(1.0,70.0,.08,false,false,false).gear)}}
 @Test fun boundedDemandNoiseCannotHuntAtEverySpeed(){for(speed in 0..144){val p=VirtualCruiseGear(virtualDriveC63Spec());p.update(1.0,speed.toDouble(),.10,true,true,false);var late=0;for(i in 1..800){val d=if(i/12%2==0)0.0 else .20;val s=p.update(1+i*.05,speed.toDouble(),d,true,false,false);if(i>200&&s.changed)late++};assertEquals("speed=$speed",0,late)}}
 @Test fun unsafeHysteresisNoiseContractRejected(){try{VirtualCruiseGear(virtualDriveC63Spec().copy(downshiftRatio=.98));fail("must reject")}catch(_:IllegalArgumentException){}}
 @Test fun highDemandPreservesShiftRpmAndAtMostOneGearPerFrame(){val p=VirtualCruiseGear(virtualDriveC63Spec());assertEquals(7000.0,p.upshiftRpm(1.0),1e-9);var prev=p.update(1.0,0.0,1.0,true,true,true);for(i in 1..400){val s=p.update(1+i*.05,144.0,1.0,true,false,false);assertTrue(kotlin.math.abs(s.gear-prev.gear)<=1);prev=s}}
 @Test fun noiseGuardChecksActualPiecewiseBoundary(){try{VirtualCruiseGear(virtualDriveC63Spec().copy(downshiftRatio=.8027),VirtualCruiseConfig(declaredDemandNoise=.105));fail("continuous guard must reject")}catch(_:IllegalArgumentException){}}
}
