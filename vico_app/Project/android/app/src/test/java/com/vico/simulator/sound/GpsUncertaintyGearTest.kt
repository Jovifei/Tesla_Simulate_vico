package com.vico.simulator.sound
import org.junit.Assert.*
import org.junit.Test

class GpsUncertaintyGearTest {
    private fun ctl(imu:Long,gps:Long=imu,u:Double?=0.0)=DriveInputControl(DriveInputSource.REAL,1,
        imu+250_000_000L,true,true,imu,gps,controlTimeElapsedNanos=imu,reportedSpeedUncertaintyMps=u)
    @Test fun boundedGpsNoiseDoesNotHuntWithReportedOrExplicitUnverifiedBuffer() {
        for(u in listOf(2.0,null)) for(initial in listOf(29.0,80.0)) {
            val c=MatlabPowertrainController(virtualDriveC63Spec())
            c.updateMeasured(0.0,initial,0.0,0.0,ctl(1_000_000_000L,u=u))
            var shifts=0
            for(i in 0..600) {
                val t=1+i*.05;val second=i/20;val speed=if(second%2==0)22.0 else 36.0
                val s=c.updateMeasured(t,speed,0.0,0.0,ctl((1e9+t*1e9).toLong(),(2L+second)*1_000_000_000L,u))
                if(i>100&&s.shiftTrigger)shifts++
            }
            assertEquals("u=$u initial=$initial",0,shifts)
        }
    }
    @Test fun invalidReportedValueCannotSilentlyBecomeUnknownFallback() {
        for(u in listOf(-1.0,Double.NaN,Double.POSITIVE_INFINITY)) {
            val point=DrivePoint(1.0,70.0,0.0,0.0);val control=ctl(1_000_000_000L,u=u)
            assertFalse(control.validatedFor(point).usable)
            val state=MatlabPowertrainController(virtualDriveC63Spec()).updateMeasured(1.0,70.0,0.0,0.0,control)
            assertFalse(state.measuredInputUsable);assertFalse(requireNotNull(state.toMappedSoundState(point,control).inputControl).usable)
        }
    }
    @Test fun uncertaintyBelongsToGpsIdentityAndNewGpsDoesNotAdvanceImuDwell() {
        val c=MatlabPowertrainController(virtualDriveC63Spec())
        val first=c.updateMeasured(1.0,70.0,0.0,0.0,ctl(1_000_000_000L,u=.1))
        val gpsOnly=c.updateMeasured(1.05,70.0,0.0,0.0,ctl(1_000_000_000L,1_050_000_000L,.2))
        assertTrue(gpsOnly.measuredInputUsable);assertEquals(first.modelContinuityRevision,gpsOnly.modelContinuityRevision)
        assertFalse(gpsOnly.shiftTrigger)
        val bad=c.updateMeasured(1.1,70.0,0.0,0.0,ctl(1_100_000_000L,1_050_000_000L,.3))
        assertFalse(bad.measuredInputUsable)
        val restored=c.updateMeasured(1.15,70.0,0.0,0.0,ctl(1_150_000_000L,u=.3))
        assertTrue(restored.measuredInputUsable);assertTrue(restored.modelContinuityRevision>first.modelContinuityRevision)
    }
    @Test fun uncertaintyDelayAndRedlineClampAreExplicitNotHiddenByForcedUpshift() {
        data class Result(val firstSpeed:Double,val clippedFrames:Int)
        fun run(u:Double?):Result {
            val c=MatlabPowertrainController(virtualDriveC63Spec());var first=Double.NaN;var clipped=0
            for(i in 0..600){val t=i*.02;val second=kotlin.math.floor(t).toLong();val v=minOf(144.0,second*12.0)
                val s=c.updateMeasured(t,v,if(t<12)12.0/3.6 else 0.0,1.0,ctl(1_000_000_000L+(t*1e9).toLong(),(1L+second)*1_000_000_000L,u))
                if(first.isNaN()&&s.gear==1&&s.rpm>=7200.0)clipped++
                if(first.isNaN()&&s.shiftTrigger)first=v
            }
            return Result(first,clipped)
        }
        val exact=run(0.0);val uncertain=run(2.0);val unknown=run(null)
        assertEquals(72.0,exact.firstSpeed,0.0);assertEquals(0,exact.clippedFrames)
        assertEquals(84.0,uncertain.firstSpeed,0.0);assertTrue(uncertain.clippedFrames>0)
        assertEquals(uncertain,unknown)
    }
}
