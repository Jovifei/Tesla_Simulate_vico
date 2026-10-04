package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

/** Black-box production entrypoint tests. Enable after source fields and policy hookup exist. */
class MeasuredAfterfireWiringTest {
    private fun spec()=MatlabPowertrainSpec(700.0,7200.0,doubleArrayOf(4.38,2.86,1.92),2.85,.335,
        2300.0,7000.0,.018,.032,.075,.055,.22,1.08,.35,.68,144.0,2600.0)
    private fun control(t:Double,frame:Long,usable:Boolean=true,epoch:Long=1L,imuT:Double=t):DriveInputControl {
        val gpsNs=1_000_000_000_000L+(t*1e9).toLong()
        val imuNs=1_000_000_000_000L+(imuT*1e9).toLong()
        return DriveInputControl(DriveInputSource.REAL,epoch,gpsNs+250_000_000L,usable,usable,
            imuSampleElapsedNanos=imuNs,gpsSampleElapsedNanos=gpsNs,controlFrameId=frame,controlTimeElapsedNanos=gpsNs,reportedSpeedUncertaintyMps=0.0)
    }
    @Test fun realMeasuredNoiseProducesZeroAfterfireWithoutAnyAdapter() {
        val c=MatlabPowertrainController(spec());var events=0;var shifts=0
        for(i in 0..600){val t=i*.05;val a=if(i%2==0)1.4 else .2
            val s=c.updateMeasured(t,40.0,a,a/3,control(t,i.toLong()))
            if(s.afterfireTrigger)events++;if(s.shiftTrigger)shifts++}
        assertEquals(0,events);assertEquals(0,shifts)
    }
    @Test fun qualifiedNegativeEpisodeProducesExactlyOneRelease() {
        val c=MatlabPowertrainController(spec());val eventTimes=mutableListOf<Double>()
        for(i in 0..160){val t=i*.05;val demand=if(t<3).6 else .0
            val accel=if(t<3)1.8 else -1.8
            if(c.updateMeasured(t,75.0,accel,demand,control(t,i.toLong())).afterfireCauseCode==1)eventTimes+=t}
        assertEquals(1,eventTimes.size)
        assertTrue(eventTimes.single()>=3.23-1e-9)
    }
    @Test fun smoothRampAllowsTwoCruiseShiftsButNoFlatCruiseRelease() {
        val c=MatlabPowertrainController(spec());var events=0;var shifts=0
        for(i in 0..600){val t=i*.05;val v=if(t<25)t*3 else 75.0;val a=if(t<25)3.0/3.6 else .0
            val s=c.updateMeasured(t,v,a,a/3,control(t,i.toLong()))
            if(s.afterfireTrigger)events++;if(s.shiftTrigger)shifts++}
        assertEquals(2,shifts);assertEquals(shifts,events)
    }
    @Test fun missingSourceCannotQualifyRealEvents() {
        val c=MatlabPowertrainController(spec());var events=0
        val unbound=DriveInputControl(DriveInputSource.REAL,1,Long.MAX_VALUE,true,true)
        for(i in 0..160){val t=i*.05;val d=if(t<3).6 else .0
            if(c.updateMeasured(t,40.0,d*3,d,unbound).afterfireTrigger)events++}
        assertEquals(0,events)
    }
    @Test fun duplicateImuSampleCannotArmFromFreshPublisherFrames() {
        val c=MatlabPowertrainController(spec());var events=0
        for(i in 0..160){val t=i*.05;val d=if(t<3).6 else .0
            if(c.updateMeasured(t,40.0,d*3,d,control(t,i.toLong(),imuT=0.0)).afterfireTrigger)events++}
        assertEquals(0,events)
    }
    @Test fun invalidRecoveryDoesNotReleaseAcrossFirstSecondOrLaterLowFrames() {
        val c=MatlabPowertrainController(spec())
        for(i in 0..20){val t=i*.05;c.updateMeasured(t,40.0,1.8,.6,control(t,i.toLong()))}
        c.updateMeasured(1.05,0.0,-1.0,.0,control(1.05,21,usable=false))
        for(i in 22..100){val t=i*.05;val d=if(i==22).6 else .0
            assertFalse(c.updateMeasured(t,40.0,d*3,d,control(t,i.toLong(),epoch=2)).afterfireTrigger)}
    }
    @Test fun eitherMissingOriginalSourcePreventsRealAfterfire() {
        for (missingGps in listOf(true,false)) {
            val c=MatlabPowertrainController(spec());var events=0
            for(i in 0..160) {
                val t=i*.05;val demand=if(t<3).6 else .0
                val original=control(t,i.toLong())
                val incomplete=if(missingGps)original.copy(gpsSampleElapsedNanos=null)
                    else original.copy(imuSampleElapsedNanos=null)
                if(c.updateMeasured(t,40.0,demand*3,demand,incomplete).afterfireTrigger)events++
            }
            assertEquals("Missing GPS=$missingGps",0,events)
        }
    }

    @Test fun duplicateImuDoesNotAdvanceShiftDwellAndActualFreshShiftIsNotDeferred() {
        val c=MatlabPowertrainController(spec())
        for(i in 0..20){val t=i*.05;c.updateMeasured(t,40.0,1.0,1.0/3,control(t,i.toLong()))}
        val duplicate=c.updateMeasured(1.05,71.0,1.0,1.0/3,control(1.05,21,imuT=1.0))
        assertFalse(duplicate.shiftTrigger);assertFalse(duplicate.afterfireTrigger)
        var shifts=0
        for(i in 22..40){val t=i*.05;val ctl=control(t,i.toLong());val s=c.updateMeasured(t,71.0,1.0,1.0/3,ctl)
            if(s.shiftTrigger){shifts++;assertTrue(s.afterfireTrigger);assertEquals(2,s.afterfireCauseCode);assertEquals(ctl.gpsSampleElapsedNanos,s.afterfireSourceId)}
            else assertFalse(s.afterfireTrigger)
        }
        assertEquals(1,shifts)
    }
}
