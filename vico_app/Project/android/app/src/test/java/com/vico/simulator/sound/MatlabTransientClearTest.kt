package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class MatlabTransientClearTest {
    private fun bank(continuous: Boolean = false): MatlabSoundBank {
        val spec = MatlabPowertrainSpec(700.0, 7200.0, doubleArrayOf(4.38, 2.86, 1.92), 2.85, .335,
            2300.0, 7000.0, .018, .032, .075, .055, .22, 1.08, .35, .68, 144.0, 2600.0)
        val loops = listOf(700.0, 7200.0).flatMap { rpm -> listOf(0.0, 1.0).map { load -> MatlabLoop(rpm, load, FloatArray(4800) { if (continuous) (kotlin.math.sin(it * .07) * .02).toFloat() else 0f }) } }
        return MatlabSoundBank("synthetic", 48000, spec, loops, FloatArray(24000) { .1f },
            listOf(MatlabTransient("shift", FloatArray(24000) { .2f })))
    }
    private fun state(time: Double, event: Boolean) = SoundState(time, 4000.0, 266.0, .5, .5, floatArrayOf(),
        false, load = .5, afterfireTrigger = event, shiftTrigger = event)

    @Test fun clearingDropsPendingEventsWithoutResettingPhaseOrStats() {
        val renderer = MatlabStatefulBankRenderer(bank())
        assertTrue(renderer.render(state(1.0, true), 960).all { it > .29f })
        val phaseField = renderer.javaClass.getDeclaredField("engineCycles").apply { isAccessible = true }
        val phase = phaseField.getDouble(renderer)
        val stats = renderer.mixStats()
        renderer.clearTransientEvents()
        assertEquals(phase, phaseField.getDouble(renderer), 0.0)
        assertEquals(stats, renderer.mixStats())
        assertTrue(renderer.render(state(1.05, false), 960).all { it == 0f })
        assertEquals(1920L, renderer.mixStats().evaluatedFrames)
        assertTrue(renderer.render(state(1.10, true), 960).all { it > .29f })
    }

    @Test fun continuousPcmIsUnchangedByEventOnlyClear() {
        val untouched = MatlabStatefulBankRenderer(bank(continuous = true))
        val cleared = MatlabStatefulBankRenderer(bank(continuous = true))
        val input = state(1.0, false)
        assertArrayEquals(untouched.render(input, 960), cleared.render(input, 960), 0f)
        cleared.clearTransientEvents()
        assertArrayEquals(untouched.render(input, 960), cleared.render(input, 960), 0f)
    }
    @Test fun expiredProducerSnapshotCannotReplayPendingEventsDuringBoundedFade() {
        val renderer = MatlabStatefulBankRenderer(bank())
        val gate = AudioInputGate()
        val envelope = GainEnvelope()
        val control = DriveInputControl(DriveInputSource.REAL, 1L, 100L, true, true)
        gate.evaluate(control, .95, 1L)
        val live = state(1.0, true).copy(inputControl = control)
        assertTrue(gate.evaluate(control, live.timeS, 2L).allowEvents)
        renderer.render(live, 960)
        repeat(30) { envelope.step(true) }
        val expired = gate.evaluate(control, live.timeS, 101L)
        assertFalse(expired.usable)
        assertTrue(expired.clearTransients)
        renderer.clearTransientEvents()
        val tail = live.copy(afterfireTrigger = false, shiftTrigger = false, shiftGain = 1.0)
        var blocks = 0
        while (envelope.value > 0f) {
            val gain = envelope.step(false)
            if (gain > 0f) assertTrue(renderer.render(tail, 960).all { it == 0f })
            blocks++
            assertTrue("Invalid input must not sustain old audio", blocks <= 20)
        }
        assertEquals(0f, envelope.value, 0f)
        assertFalse(gate.evaluate(control, live.timeS, 1000L).usable)
    }

    @Test fun normalStopClearsAlreadyQueuedLegacyEventsBeforeTail() {
        val renderer=MatlabStatefulBankRenderer(bank())
        val gate=AudioInputGate()
        val c=DriveInputControl(DriveInputSource.REAL,1,Long.MAX_VALUE,true,true)
        gate.evaluate(c,.9,1L,true)
        val live=state(1.0,true).copy(inputControl=c)
        renderer.render(live,960)
        val stopped=selectAudioWriterSnapshot(false,live,live)!!
        assertTrue(gate.evaluate(c,stopped.timeS,2L,false).clearTransients)
        renderer.clearTransientEvents()
        assertTrue(renderer.render(stopped,960).all { it==0f })
    }
}
