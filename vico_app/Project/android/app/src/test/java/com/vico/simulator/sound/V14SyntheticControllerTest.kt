package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class V14SyntheticControllerTest {
    @Test fun atomicFrameReachesExistingSoundStateWithoutInventingGearMeaning() {
        var delivered: SoundState? = null
        val controller = V14SyntheticController { delivered = it }
        val owner = controller.begin()
        assertTrue(controller.submit(owner, 1, 100, 1_000, 0.1, V14SyntheticFrame(.25, 2400.0, .7, -1)))
        val state = requireNotNull(delivered)
        assertEquals(.25, state.throttle, 0.0); assertEquals(2400.0, state.rpm, 0.0)
        assertEquals(.7, state.load, 0.0); assertEquals(-1, state.gear)
        assertFalse(state.shiftTrigger); assertFalse(state.afterfireTrigger)
        val gate = AudioInputGate()
        assertTrue(gate.evaluate(state.inputControl, state.timeS, 1_000).usable)
        assertFalse(gate.evaluate(state.inputControl, state.timeS, 1_001).usable)
    }

    @Test fun invalidOrStoppedFramesCannotResurrectAndOldOwnerCannotStopNewOwner() {
        var delivered: SoundState? = null
        val controller = V14SyntheticController { delivered = it }
        val old = controller.begin(); val current = controller.begin()
        assertFalse(controller.submit(old, 1, 100, 1_000, 0.1, V14SyntheticFrame(.1, 800.0, .2, 1)))
        assertTrue(controller.submit(current, 1, 100, 1_000, 0.1, V14SyntheticFrame(.1, 800.0, .2, 1)))
        controller.stop(old); assertNotNull(delivered)
        assertFalse(controller.submit(current, 2, 100, 1_000, 0.2, V14SyntheticFrame(.1, Double.NaN, .2, 1)))
        assertNull(delivered)
        assertFalse(controller.submit(current, 3, 100, 1_000, 0.3, V14SyntheticFrame(.1, 800.0, .2, 1)))
        val fresh = controller.begin()
        assertTrue(controller.submit(fresh, 1, 100, 1_000, 0.1, V14SyntheticFrame(.1, 800.0, .2, 1)))
        controller.stop(fresh); assertNull(delivered)
        assertFalse(controller.submit(fresh, 2, 100, 1_000, 0.2, V14SyntheticFrame(.1, 800.0, .2, 1)))
        val cancelled = controller.begin(); controller.cancel()
        assertFalse(controller.submit(cancelled, 1, 100, 1_000, 0.1, V14SyntheticFrame(.1, 800.0, .2, 1)))
    }

    @Test fun duplicateSequenceAndUnboundedValidityFailClosed() {
        var delivered: SoundState? = null
        val controller = V14SyntheticController { delivered = it }; val owner = controller.begin()
        assertTrue(controller.submit(owner, 1, 100, 1_000, 0.1, V14SyntheticFrame(.1, 800.0, .2, 1)))
        assertFalse(controller.submit(owner, 1, 100, 1_000, 0.2, V14SyntheticFrame(.1, 800.0, .2, 1)))
        assertNull(delivered)
        val fresh = controller.begin()
        assertFalse(controller.submit(fresh, 1, 100, 2_000_000_101L, 0.1, V14SyntheticFrame(.1, 800.0, .2, 1)))
    }

    @Test fun backwardsTimeRejectsTheFrameAndClearsTheOwnedState() {
        var delivered: SoundState? = null
        val controller = V14SyntheticController { delivered = it }; val owner = controller.begin()
        assertTrue(controller.submit(owner, 1, 100, 1_000, 1.0, V14SyntheticFrame(.1, 800.0, .2, 1)))
        assertFalse(controller.submit(owner, 2, 101, 1_000, .9, V14SyntheticFrame(.2, 900.0, .3, 2)))
        assertNull(delivered)
    }
}
