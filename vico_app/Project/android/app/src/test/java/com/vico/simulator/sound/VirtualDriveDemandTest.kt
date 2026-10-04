package com.vico.simulator.sound
import org.junit.Test
import org.junit.Assert.*
class VirtualDriveDemandTest {
 private fun point(t:Double,speed:Double=70.0/3.6,a:Double=0.0,gps:Double=t,epoch:Long=1)=VirtualDemandInput(epoch,true,(gps*1e9).toLong(),(t*1e9).toLong(),speed,a)
 @Test fun cruiseHasPositiveDemandAndExplicitAssetCoordinate(){val s=VirtualDriveDemand().update(point(1.0))!!;assertTrue(s.demand>0);assertEquals(.32+.6*s.demand,s.bankLoad,1e-12)}
 @Test fun confirmedStationaryThenLaunchExitsImmediatelyEvenGpsStillZero(){val e=VirtualDriveDemand();var s=e.update(point(1.0,0.0))!!;for(i in 1..15)s=e.update(point(1+i*.05,0.0))!!;assertTrue(s.parked);assertEquals(0.0,s.demand,0.0);s=e.update(point(1.8,0.0,2.0))!!;assertFalse(s.parked);assertTrue(s.demand>0)}
 @Test fun repeatedSourceNeverAdvancesFilterOrDwell(){val e=VirtualDriveDemand();val s=e.update(point(1.0,a=-.5))!!;repeat(1000){val n=e.update(point(1.0,a=-.5))!!;assertEquals(s.demand,n.demand,0.0);assertFalse(n.sustainedDeceleration);assertFalse(n.freshImu)}}
 @Test fun gpsOnlyChangesRoadTermButNotImuDwell(){val e=VirtualDriveDemand();val a=e.update(point(1.0,0.0,-.5))!!;val b=e.update(point(1.0,40.0,-.5,gps=1.2))!!;assertEquals(a.filteredAccelerationMps2,b.filteredAccelerationMps2,0.0);assertFalse(b.sustainedDeceleration);assertFalse(b.freshImu);assertTrue(b.demand>a.demand)}
 @Test fun invalidRecoveryReanchorsWithoutZeroRampOrInheritedDeceleration(){val e=VirtualDriveDemand();for(i in 0..10)e.update(point(1+i*.05,a=-.5));e.invalidate();val s=e.update(point(3.0,a=.8))!!;assertTrue(s.resumed);assertEquals(.8,s.filteredAccelerationMps2,0.0);assertFalse(s.sustainedDeceleration)}
 @Test fun speedOnlyStopsCannotCreateParkWhileAccelerating(){val e=VirtualDriveDemand();for(i in 0..20)assertFalse(e.update(point(1+i*.05,0.0,2.0))!!.parked)}
 @Test fun positiveAccelerationToCruiseIsNeverDeceleration(){val e=VirtualDriveDemand();for(i in 0..40){val s=e.update(point(1+i*.05,a=if(i<20)1.5 else 0.0))!!;assertFalse(s.sustainedDeceleration)}}
 @Test fun sampleRateInvariance(){val values= listOf(10,20,50).map{hz->val e=VirtualDriveDemand();e.update(point(1.0,a=0.0));var s=e.update(point(1+1.0/hz,a=1.0))!!;for(i in 2..hz)s=e.update(point(1+i.toDouble()/hz,a=1.0))!!;s.demand};assertTrue(values.max()-values.min()<1e-12)}
 @Test fun rejectsInvalidAndOldWithoutResettingNewEpoch(){val e=VirtualDriveDemand();assertNotNull(e.update(point(1.0,epoch=2)));assertNull(e.update(point(2.0,epoch=1)));assertNull(e.update(point(2.0,speed=Double.NaN)));assertTrue(e.update(point(3.0,epoch=2))!!.resumed)}
 @Test fun aSourceIdentityCannotBeReusedForDifferentValues(){val e=VirtualDriveDemand();e.update(point(1.0,a=1.0));assertNull(e.update(point(1.0,a=0.0,gps=1.1)));val recovered=e.update(point(1.1,a=0.0,gps=1.1))!!;assertTrue(recovered.resumed);assertEquals(0.0,recovered.filteredAccelerationMps2,0.0)}
 @Test fun finiteInputOverflowFailsClosedAndNormalInputCanRecover(){val e=VirtualDriveDemand();assertNull(e.update(point(1.0,speed=Double.MAX_VALUE)));assertTrue(e.update(point(1.05))!!.resumed)}
}
