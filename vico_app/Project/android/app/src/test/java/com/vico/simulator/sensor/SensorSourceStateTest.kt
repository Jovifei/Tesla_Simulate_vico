package com.vico.simulator.sensor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class SensorSourceStateTest {

    @Test
    fun disabling_demo_immediately_returns_the_latest_real_sample() {
        val state = SensorSourceState()
        state.updateReal(SensorFrame(42.0, 0.35, true, floatArrayOf(0f, 0.35f, 0f)))
        state.setDemoMode(true)
        state.updateDemo(SensorFrame(144.0, 2.5, true, floatArrayOf(0f, 2.5f, 0f)))

        val restored = state.setDemoMode(false)

        assertEquals(42.0, restored.speedKmh, 1e-9)
        assertEquals(0.35, restored.forwardAccelMps2, 1e-9)
        assertFalse(state.isDemoMode)
    }
}
