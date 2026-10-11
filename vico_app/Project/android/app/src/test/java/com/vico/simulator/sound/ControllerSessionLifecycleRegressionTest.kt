package com.vico.simulator.sound

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Session lifecycle regression coverage.
 *
 * The test compares a reused controller after an explicit session boundary with a
 * fresh controller. Provenance identity is allowed to advance; controller state
 * and event history must not leak across the restart boundary.
 */
class ControllerSessionLifecycleRegressionTest {
    private fun update(
        controller: MatlabPowertrainController,
        t: Double,
        speed: Double,
        accel: Double,
        sourceNanos: Long,
    ): MatlabPowertrainState = controller.updateMeasured(
        t,
        speed,
        accel,
        (accel / 3.0).coerceIn(0.0, 1.0),
        DriveInputControl(
            DriveInputSource.REAL,
            epoch = 7L,
            validUntilElapsedNanos = sourceNanos + 250_000_000L,
            speedUsable = true,
            accelerationUsable = true,
            gpsSampleElapsedNanos = sourceNanos,
            imuSampleElapsedNanos = sourceNanos,
            controlTimeElapsedNanos = sourceNanos,
        ),
    )

    @Test
    fun sameEpochMonotonicRestartMatchesFreshControllerAfterSessionReset() {
        val reused = MatlabPowertrainController(virtualDriveC63Spec())
        var before = update(reused, 1.0, 20.0, 2.0, 1_000_000_000L)
        for (i in 1..120) {
            before = update(reused, 1.0 + i * 0.05, 120.0, 2.0, 1_000_000_000L + i * 50_000_000L)
        }
        assertTrue(before.gear > 1)

        val afterReset = reused.resetSession()
        val fresh = MatlabPowertrainController(virtualDriveC63Spec())
            .let { update(it, 10.0, 0.0, 0.0, 10_000_000_000L) }
        val restarted = update(reused, 10.0, 0.0, 0.0, 10_000_000_000L)

        assertTrue(afterReset)
        assertEquals(fresh.gear, restarted.gear)
        assertEquals(fresh.rpm, restarted.rpm, 1e-9)
        assertEquals(fresh.virtualDemand, restarted.virtualDemand)
        assertFalse(restarted.shiftTrigger)
        assertFalse(restarted.afterfireTrigger)
        assertEquals(0, restarted.afterfireCauseCode)
    }
}
