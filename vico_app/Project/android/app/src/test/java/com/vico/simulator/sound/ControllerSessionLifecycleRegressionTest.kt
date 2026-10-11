package com.vico.simulator.sound

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Session lifecycle regression coverage.
 *
 * This deliberately compares a reused synthetic controller against a fresh
 * controller. It documents the retained-state boundary without changing the
 * renderer phase/transient policy.
 */
class ControllerSessionLifecycleRegressionTest {
    private fun drive(controller: MatlabPowertrainController, start: Double): MatlabPowertrainState {
        var state = controller.update(start, 20.0, 2.0, 0.8)
        for (i in 1..120) {
            state = controller.update(start + i * 0.05, 120.0, 2.0, 0.9)
        }
        return state
    }

    @Test
    fun sameVehicleRestartNeedsFreshControllerOrExplicitSessionReset() {
        val reused = MatlabPowertrainController(virtualDriveC63Spec())
        val first = drive(reused, 1.0)
        assertTrue(first.gear > 1)

        val retained = reused.update(10.0, 0.0, 0.0, 0.0)
        val fresh = MatlabPowertrainController(virtualDriveC63Spec())
            .update(0.0, 0.0, 0.0, 0.0)

        assertTrue(retained.gear >= fresh.gear)
        assertEquals(1, fresh.gear)
    }
}
