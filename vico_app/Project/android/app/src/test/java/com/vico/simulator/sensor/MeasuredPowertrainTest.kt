package com.vico.simulator.sensor
import com.vico.simulator.sound.*
import org.junit.Assert.*
import org.junit.Test

class MeasuredPowertrainTest {
    private fun spec()=MatlabPowertrainSpec(700.0,7200.0,doubleArrayOf(4.38,2.86,1.92),2.85,.335,2300.0,7000.0,.018,.032,.075,.055,.22,1.08,.35,.68,144.0)
    private var sourceSequence = 0L
    private fun control(epoch:Long=1,ok:Boolean=true,sourceTimeS:Double?=null):DriveInputControl {
        val source = 1_000_000_000_000L + (sourceTimeS?.let { (it*1e9).toLong() } ?: (++sourceSequence*50_000_000L))
        return DriveInputControl(DriveInputSource.REAL,epoch,Long.MAX_VALUE,ok,ok,imuSampleElapsedNanos=source,gpsSampleElapsedNanos=source,controlTimeElapsedNanos=source)
    }
    @Test fun lossAndRecoveryPreserveGearAndDoNotPlayFakeShiftOrAfterfire() {
        val c=MatlabPowertrainController(spec())
        c.updateMeasured(0.0,0.0,1.2,.5,control())
        var s=c.updateMeasured(1.0,80.0,1.2,.5,control())
        assertEquals(2,s.gear)
        s=c.updateMeasured(1.05,0.0,-2.0,0.0,control(2,false))
        assertEquals(2,s.gear);assertFalse(s.shiftTrigger);assertFalse(s.afterfireTrigger)
        s=c.updateMeasured(2.0,70.0,1.2,.4,control(3))
        assertEquals(2,s.gear);assertFalse(s.shiftTrigger);assertFalse(s.afterfireTrigger)
        s=c.updateMeasured(2.05,70.0,1.2,.4,control(3))
        assertEquals(2,s.gear);assertFalse(s.shiftTrigger);assertFalse(s.afterfireTrigger)
    }
    @Test fun skippedInvalidFrameStillResetsTransientHistoryByEpoch() {
        val c=MatlabPowertrainController(spec())
        c.updateMeasured(0.0,80.0,2.4,.8,control())
        val s=c.updateMeasured(.05,80.0,0.0,0.0,control(3))
        assertFalse(s.afterfireTrigger);assertFalse(s.shiftTrigger)
        assertFalse(c.updateMeasured(.10,80.0,0.0,0.0,control(3)).afterfireTrigger)
    }
    @Test fun freshRampHasNoArtificialSpeedScaleAndOneC63Shift() {
        val c=MatlabPowertrainController(spec());var count=0
        for(i in 0..160) { val s=c.updateMeasured(i*.05,i*.5,1.2,.4,control()); if(s.shiftTrigger)count++ }
        assertEquals(1,count)
    }
    @Test fun invalidOrientationDoesNotConsumeHugeAccelerationOrSpeedIntoGear() {
        val c=MatlabPowertrainController(spec())
        val input=DriveInputControl(DriveInputSource.REAL,1,Long.MAX_VALUE,true,false)
        val s=c.updateMeasured(1.0,120.0,100.0,1.0,input)
        assertEquals(1,s.gear);assertEquals(700.0,s.rpm,0.0)
        assertFalse(s.afterfireTrigger);assertFalse(s.shiftTrigger)
    }
    @Test fun changingSecondRecoveryFrameCannotEmitAResumeAfterfire() {
        val c=MatlabPowertrainController(spec())
        c.updateMeasured(0.0,80.0,2.4,.8,control())
        assertFalse(c.updateMeasured(.05,80.0,0.0,0.0,control()).afterfireTrigger)
        c.updateMeasured(.10,80.0,2.4,.8,control())
        assertFalse(c.updateMeasured(.15,80.0,0.0,0.0,control()).afterfireTrigger)
        // A valid release now needs fresh source samples and both qualification dwells.
        for(i in 0..5) { val t=.50+i*.05; c.updateMeasured(t,80.0,2.4,.8,control(sourceTimeS=t)) }
        assertFalse(c.updateMeasured(.80,80.0,0.0,0.0,control(sourceTimeS=.80)).afterfireTrigger)
        assertTrue(c.updateMeasured(.90,80.0,0.0,0.0,control(sourceTimeS=.90)).afterfireTrigger)
    }
    @Test fun releaseInsideRecoveryIsNotDelayedUntilWindowEnds() {
        val c=MatlabPowertrainController(spec())
        c.updateMeasured(0.0,80.0,2.4,.8,control())
        c.updateMeasured(.34,80.0,2.4,.8,control())
        assertFalse(c.updateMeasured(.36,80.0,0.0,0.0,control()).afterfireTrigger)
        assertFalse(c.updateMeasured(.40,80.0,0.0,0.0,control()).afterfireTrigger)
        // A valid release now needs fresh source samples and both qualification dwells.
        for(i in 0..5) { val t=.50+i*.05; c.updateMeasured(t,80.0,2.4,.8,control(sourceTimeS=t)) }
        assertFalse(c.updateMeasured(.80,80.0,0.0,0.0,control(sourceTimeS=.80)).afterfireTrigger)
        assertTrue(c.updateMeasured(.90,80.0,0.0,0.0,control(sourceTimeS=.90)).afterfireTrigger)
    }
    @Test fun nonFiniteMeasuredPointInvalidatesThePublishedControlContract() {
        val valid=DrivePoint(1.0,70.0,.5,1.5,false)
        for (p in listOf(valid.copy(speedKmh=Double.NaN),valid.copy(accelMps2=Double.POSITIVE_INFINITY),
                         valid.copy(throttle=Double.NaN),valid.copy(timeS=Double.NaN),valid.copy(speedKmh=-1.0))) {
            val checked=control().validatedFor(p)
            assertFalse(checked.usable)
            assertFalse(checked.speedUsable);assertFalse(checked.accelerationUsable)
        }
        assertTrue(control().validatedFor(valid).usable)
    }
}
