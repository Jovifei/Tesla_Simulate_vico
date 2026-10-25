package com.vico.simulator.sound

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The policy used by the production writer, before muted/stale state is replaced by its tail. */
class CoordinatedVoiceLifecycleRegressionTest {
    private val demo = DriveInputControl(DriveInputSource.DEMO, 7L, Long.MAX_VALUE, true, true)
    private fun accepts(
        lifecycle: CoordinatedVoiceLifecycle, control: DriveInputControl? = demo,
        available: Boolean = true, running: Boolean = true, muted: Boolean = false,
        transition: Boolean = false,
    ) = lifecycle.acceptsInput(control, available, running, muted, transition)

    @Test fun ordinaryBankPolicyDoesNotLatchCandidateRejection() {
        val lifecycle = CoordinatedVoiceLifecycle()
        lifecycle.requestCancellation()
        assertTrue(accepts(lifecycle, null, available = false, running = false, muted = true, transition = true))
        assertTrue(accepts(lifecycle))
    }

    @Test fun firstValidDemoTransitionKeepsFreshPreparationArmed() {
        val lifecycle = CoordinatedVoiceLifecycle().also { it.prepare() }
        assertTrue(accepts(lifecycle, transition = true))
        assertTrue(accepts(lifecycle))
    }

    @Test fun laterInputTransitionRejectsUntilExplicitPreparation() {
        val lifecycle = CoordinatedVoiceLifecycle().also { it.prepare() }
        assertTrue(accepts(lifecycle, transition = true))
        assertFalse(accepts(lifecycle, demo.copy(epoch = 8L), transition = true))
        assertFalse(accepts(lifecycle))
        lifecycle.prepare()
        assertTrue(accepts(lifecycle, transition = true))
    }

    @Test fun unavailableMutedStoppedAndWrongSourceRemainRejectedAfterRecovery() {
        val rejections = listOf<(CoordinatedVoiceLifecycle) -> Boolean>(
            { accepts(it, available = false) },
            { accepts(it, null) },
            { accepts(it, demo.copy(source = DriveInputSource.PREVIEW)) },
            { accepts(it, muted = true) },
            { accepts(it, running = false) },
        )
        for (reject in rejections) {
            val lifecycle = CoordinatedVoiceLifecycle().also { it.prepare() }
            assertTrue(accepts(lifecycle, transition = true))
            assertFalse(reject(lifecycle))
            repeat(25) { assertFalse(accepts(lifecycle)) }
        }
    }

    @Test fun ownerRequestSurvivesMuteClearingBeforeWriterObservesIt() {
        val lifecycle = CoordinatedVoiceLifecycle().also { it.prepare() }
        assertTrue(accepts(lifecycle, transition = true))
        lifecycle.requestCancellation()
        assertFalse(accepts(lifecycle, muted = false))
        assertFalse(accepts(lifecycle))
        lifecycle.prepare()
        assertTrue(accepts(lifecycle, transition = true))
    }

    @Test fun controllerResetRestoresDefaultBankAdmission() {
        val lifecycle = CoordinatedVoiceLifecycle().also { it.prepare() }
        lifecycle.requestCancellation()
        assertFalse(accepts(lifecycle))
        lifecycle.clear()
        assertTrue(accepts(lifecycle, null, available = false, transition = true))
        assertTrue(accepts(lifecycle))
    }
}
