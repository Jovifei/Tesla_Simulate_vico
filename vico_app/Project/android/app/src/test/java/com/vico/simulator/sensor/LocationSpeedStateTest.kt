package com.vico.simulator.sensor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LocationSpeedStateTest {
    @Test
    fun stale_cached_fix_is_rejected() {
        val state = LocationSpeedState()

        val accepted = state.update(
            speedMps = 22.0,
            hasSpeed = true,
            fixElapsedNanos = 1_000_000_000L,
            nowElapsedNanos = 6_000_000_000L,
        )

        assertFalse(accepted)
        assertEquals(0.0, state.speedKmh, 0.0)
        assertFalse(state.gpsOk)
    }

    @Test
    fun current_fix_expires_to_zero_speed() {
        val state = LocationSpeedState()
        assertTrue(state.update(10.0, true, 5_000_000_000L, 5_500_000_000L))
        assertEquals(36.0, state.speedKmh, 0.001)

        state.expire(9_000_000_000L)

        assertEquals(0.0, state.speedKmh, 0.0)
        assertFalse(state.gpsOk)
    }
}
