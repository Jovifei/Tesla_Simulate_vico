package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class AudioInputGateTest {
    private fun real(epoch: Long = 1L, deadline: Long = 100L, speed: Boolean = true, accel: Boolean = true) =
        DriveInputControl(DriveInputSource.REAL, epoch, deadline, speed, accel)

    @Test fun nullUnspecifiedAndPartialTrustFailClosed() {
        val gate = AudioInputGate()
        assertFalse(gate.evaluate(null, 0.0, 1L).usable)
        assertFalse(gate.evaluate(DriveInputControl(DriveInputSource.UNSPECIFIED, 0L, Long.MAX_VALUE, true, true), 0.0, 1L).usable)
        assertFalse(gate.evaluate(real(speed = false), 0.0, 1L).usable)
        assertFalse(gate.evaluate(real(accel = false), 0.0, 1L).usable)
        assertFalse(gate.evaluate(real(deadline = 0L), 0.0, 0L).usable)
        assertFalse(gate.evaluate(real(), Double.NaN, 1L).usable)
    }

    @Test fun writerWatchdogExpiresWithoutAnotherProducerUpdate() {
        val gate = AudioInputGate()
        val control = real()
        assertTrue(gate.evaluate(control, 1.0, 1L).usable)
        assertTrue(gate.evaluate(control, 1.0, 99L).usable)
        assertTrue(gate.evaluate(control, 1.0, 100L).usable)
        val expiry = gate.evaluate(control, 1.0, 101L)
        assertFalse(expiry.usable)
        assertTrue(expiry.clearTransients)
        assertFalse(gate.evaluate(control, 1.0, 102L).clearTransients)
        assertFalse(gate.evaluate(control, 1.0, Long.MAX_VALUE).usable)
    }

    @Test fun recoverySuppressesWholeInitialSnapshotThenAcceptsFreshState() {
        val gate = AudioInputGate()
        assertFalse(gate.evaluate(real(), 1.0, 1L).allowEvents)
        assertFalse(gate.evaluate(real(), 1.0, 2L).allowEvents)
        assertTrue(gate.evaluate(real(), 1.05, 3L).allowEvents)
        gate.evaluate(real(), 1.05, 101L)
        val recovery = real(deadline = 300L)
        assertFalse(gate.evaluate(recovery, 1.10, 101L).allowEvents)
        assertFalse(gate.evaluate(recovery, 1.10, 102L).allowEvents)
        assertTrue(gate.evaluate(recovery, 1.15, 103L).allowEvents)
    }

    @Test fun sourceAndEpochChangesClearOldEvents() {
        val gate = AudioInputGate()
        gate.evaluate(real(), 0.0, 1L)
        val demo = DriveInputControl(DriveInputSource.DEMO, 1L, 0L, true, true)
        val synthetic = gate.evaluate(demo, 0.0, 2L)
        assertTrue(synthetic.usable)
        assertTrue(synthetic.clearTransients)
        assertTrue(synthetic.allowEvents)
        assertTrue(gate.evaluate(real(), 1.0, 3L).clearTransients)
        assertFalse(gate.evaluate(real(), 1.0, 4L).allowEvents)
        assertTrue(gate.evaluate(real(epoch = 2L), 1.1, 5L).clearTransients)
        assertFalse(gate.evaluate(real(epoch = 2L), 1.1, 6L).allowEvents)
    }

    @Test fun explicitSyntheticModesArePermittedButUnusableOnesAreNot() {
        for (source in listOf(DriveInputSource.DEMO, DriveInputSource.PREVIEW, DriveInputSource.QUALIFICATION)) {
            val gate = AudioInputGate()
            assertTrue(gate.evaluate(DriveInputControl(source, 1L, 0L, true, true), 0.0, Long.MAX_VALUE).usable)
            assertFalse(gate.evaluate(DriveInputControl(source, 1L, 0L, true, false), 0.0, 1L).usable)
        }
    }
    @Test fun prototypeRejectsRealAndCannotResumeOldQueueWithoutPreparation() {
        val guard = PrototypeInputGuard()
        val qualification = DriveInputControl(DriveInputSource.QUALIFICATION, 1L, Long.MAX_VALUE, true, true)
        assertTrue(guard.accept(qualification, true))
        assertFalse(guard.accept(real(), true))
        assertFalse(guard.accept(qualification, true))
        guard.resetForExplicitPreparation()
        assertTrue(guard.accept(qualification, true))
        assertFalse(guard.accept(qualification, false))
        assertFalse(guard.accept(qualification, true))
    }

    @Test fun prototypeRejectsEveryUnqualifiedSource() {
        for (source in listOf(DriveInputSource.UNSPECIFIED, DriveInputSource.REAL, DriveInputSource.DEMO, DriveInputSource.PREVIEW)) {
            assertFalse(PrototypeInputGuard().accept(DriveInputControl(source, 1L, Long.MAX_VALUE, true, true), true))
        }
        assertFalse(PrototypeInputGuard().accept(null, true))
    }

    @Test fun stoppingConsumesOnlyTheVerifiedEventFreeTail() {
        val qualified = SoundState(1.0,4000.0,266.0,.5,.5,floatArrayOf(),false,
            afterfireTrigger=true,shiftTrigger=true,
            inputControl=DriveInputControl(DriveInputSource.QUALIFICATION,0,Long.MAX_VALUE,true,true))
        val restoredReal=qualified.copy(inputControl=DriveInputControl(DriveInputSource.REAL,2,100,true,true))
        val tail=selectAudioWriterSnapshot(false,restoredReal,qualified)
        assertNotNull(tail)
        assertEquals(DriveInputSource.QUALIFICATION,tail!!.inputControl!!.source)
        assertFalse(tail.afterfireTrigger);assertFalse(tail.shiftTrigger)
        assertTrue(PrototypeInputGuard().accept(tail.inputControl,true))
        assertEquals(restoredReal,selectAudioWriterSnapshot(true,restoredReal,qualified))
        assertNull(selectAudioWriterSnapshot(false,restoredReal,null))
    }
    @Test fun normalStopClearsPendingEventsEvenWithoutAnEpochChange() {
        val gate=AudioInputGate()
        val c=DriveInputControl(DriveInputSource.REAL,1,Long.MAX_VALUE,true,true)
        gate.evaluate(c,1.0,1L,true)
        assertFalse(gate.evaluate(c,1.1,2L,true).clearTransients)
        val stopping=gate.evaluate(c,1.1,3L,false)
        assertTrue(stopping.clearTransients);assertFalse(stopping.allowEvents)
        assertFalse(gate.evaluate(c,1.1,4L,false).clearTransients)
    }
    @Test fun stopRestoreInterleavingsNeverPromoteRealIntoQualificationTail() {
        val q=SoundState(1.0,4000.0,266.0,.5,.5,floatArrayOf(),false,
            inputControl=DriveInputControl(DriveInputSource.QUALIFICATION,0,Long.MAX_VALUE,true,true))
        val real=q.copy(inputControl=DriveInputControl(DriveInputSource.REAL,1,100L,true,true))
        // Actual adapter reads current before running. Model every point where stop+restore may occur.
        for (stopAt in 0..2) {
            var current=q;var running=true
            fun stopRestore(){running=false;current=real}
            if(stopAt==0)stopRestore()
            val published=current
            if(stopAt==1)stopRestore()
            val writerRunning=running
            if(stopAt==2)stopRestore()
            val selected=selectAudioWriterSnapshot(writerRunning,published,q)!!
            assertEquals(DriveInputSource.QUALIFICATION,selected.inputControl!!.source)
        }
    }
}
