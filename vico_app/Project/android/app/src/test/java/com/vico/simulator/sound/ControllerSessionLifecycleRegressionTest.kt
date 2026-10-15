package com.vico.simulator.sound

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Session lifecycle regression coverage.
 *
 * A reset keeps provenance/session identity semantics separate from controller
 * state. The restarted same-epoch controller must match a fresh controller.
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

    private fun assertFreshAfterMeasuredRestart(speed: Double) {
        val reused = MatlabPowertrainController(virtualDriveC63Spec())
        for (i in 0..120) {
            update(reused, 1.0 + i * 0.05, 120.0, 2.0, 1_000_000_000L + i * 50_000_000L)
        }
        assertTrue(reused.resetSession())

        val restarted = update(reused, 20.0, speed, 0.0, 20_000_000_000L)
        val fresh = update(
            MatlabPowertrainController(virtualDriveC63Spec()),
            20.0,
            speed,
            0.0,
            20_000_000_000L,
        )

        assertEquals(fresh.gear, restarted.gear)
        assertEquals(fresh.rpm, restarted.rpm, 1e-9)
        assertEquals(fresh.virtualDemand, restarted.virtualDemand)
        assertFalse(restarted.shiftTrigger)
        assertFalse(restarted.afterfireTrigger)
        assertEquals(0, restarted.afterfireCauseCode)
    }
    @Test
    fun sameEpochMonotonicRestartMatchesFreshControllerAfterSessionReset() = assertFreshAfterMeasuredRestart(70.0)

    @Test
    fun realHysteresisOverlapRestartMatchesFreshGear() = assertFreshAfterMeasuredRestart(30.0)

    @Test
    fun syntheticRestartDropsHighGearHistory() {
        val reused = MatlabPowertrainController(virtualDriveC63Spec())
        for (i in 0..120) reused.update(1.0 + i * .05, 120.0, 2.0, .8)
        assertTrue(reused.resetSession())
        val restarted = reused.update(20.0, 0.0, 0.0, 0.0)
        val fresh = MatlabPowertrainController(virtualDriveC63Spec()).update(20.0, 0.0, 0.0, 0.0)
        assertEquals(fresh.gear, restarted.gear)
        assertEquals(fresh.rpm, restarted.rpm, 1e-9)
        assertFalse(restarted.shiftTrigger)
        assertFalse(restarted.afterfireTrigger)
    }
}
