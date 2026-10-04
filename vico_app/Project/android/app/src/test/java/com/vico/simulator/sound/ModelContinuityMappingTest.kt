package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class ModelContinuityMappingTest {
    private fun control(ns: Long) = DriveInputControl(DriveInputSource.REAL, 7L, ns+250_000_000L,
        true, true, ns, ns, controlTimeElapsedNanos=ns)
    private fun step(c: MatlabPowertrainController, ns:Long, accel:Double=1.0, ctl:DriveInputControl=control(ns)):SoundState {
        val point=DrivePoint(ns/1e9,70.0,(accel/3).coerceIn(0.0,1.0),accel)
        return c.updateMeasured(point.timeS,point.speedKmh,accel,point.throttle,ctl).toMappedSoundState(point,ctl)
    }
    @Test fun hiddenInvalidCannotDisappearAcrossLatestStateMailbox() {
        val c=MatlabPowertrainController(virtualDriveC63Spec());val gate=AudioInputGate()
        var s=step(c,1_000_000_000L);gate.evaluate(s.inputControl,s.timeS,1_000_000_000L)
        s=step(c,1_050_000_000L);assertFalse(gate.evaluate(s.inputControl,s.timeS,1_050_000_000L).clearTransients)
        val a=requireNotNull(s.inputControl)
        val hidden=step(c,1_100_000_000L,ctl=control(1_100_000_000L).copy(imuSampleElapsedNanos=900_000_000L))
        assertFalse(requireNotNull(hidden.inputControl).usable)
        // Deliberately omit hidden from the writer. B may also be skipped; its revision persists in C.
        val b=step(c,1_150_000_000L,0.0);val next=step(c,1_200_000_000L,0.0)
        val ctl=requireNotNull(next.inputControl)
        assertEquals(a.epoch,ctl.epoch);assertTrue(ctl.modelContinuityRevision>a.modelContinuityRevision)
        assertEquals(requireNotNull(b.inputControl).modelContinuityRevision,ctl.modelContinuityRevision)
        val resumed=gate.evaluate(ctl,next.timeS,1_200_000_000L)
        assertTrue(resumed.clearTransients);assertFalse(resumed.allowEvents)
        assertFalse(gate.evaluate(ctl,next.timeS,1_210_000_000L).allowEvents)
        val fresh=step(c,1_250_000_000L,0.0)
        assertTrue(gate.evaluate(fresh.inputControl,fresh.timeS,1_250_000_000L).allowEvents)
    }
    @Test fun duplicateAndGpsOnlyUpdatesRetainSegmentRevision() {
        val c=MatlabPowertrainController(virtualDriveC63Spec());val first=step(c,1_000_000_000L)
        val revision=requireNotNull(first.inputControl).modelContinuityRevision
        val gps=step(c,1_050_000_000L,ctl=control(1_050_000_000L).copy(imuSampleElapsedNanos=1_000_000_000L))
        assertEquals(revision,requireNotNull(gps.inputControl).modelContinuityRevision)
    }
    @Test fun referenceMappingKeepsExplicitSyntheticControlIdentity() {
        val point=DrivePoint(1.0,40.0,.4,1.2);val legacy=MatlabPowertrainController(virtualDriveC63Spec()).update(1.0,40.0,1.2,.4)
        val ctl=DriveInputControl(DriveInputSource.QUALIFICATION,11,Long.MAX_VALUE,true,true)
        val state=legacy.toMappedSoundState(point,ctl)
        assertSame(ctl,state.inputControl);assertEquals(.4,state.throttle,0.0)
        assertEquals(legacy.load,state.load,0.0);assertEquals(legacy.torqueGain,state.shiftGain,0.0)
        assertEquals(0L,requireNotNull(state.inputControl).modelContinuityRevision)
    }
}
