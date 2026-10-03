package com.vico.simulator.sensor

import org.junit.Assert.*
import org.junit.Test

class LinearAccelerationStateTest {
    @Test fun latest_measurement_keeps_all_three_device_axes_without_smoothing() {
        val state = LinearAccelerationState()
        val sample = floatArrayOf(1f, -2.5f, 3f)
        assertTrue(state.update(sample, 1_000_000_000L, 1_010_000_000L))
        sample[1] = 100f
        assertArrayEquals(floatArrayOf(1f, -2.5f, 3f), state.sample(), 0f)
        state.sample()[1] = 200f
        assertEquals(-2.5f, state.sample()[1], 0f)
    }

    @Test fun stale_out_of_order_duplicate_and_future_events_do_not_replace_current_measurement() {
        val state = LinearAccelerationState()
        val fresh = floatArrayOf(0f, 2f, 0f)
        assertTrue(state.update(fresh, 2_000_000_000L, 2_010_000_000L))
        for (stamp in listOf(1_900_000_000L, 2_000_000_000L, 2_100_000_000L, 0L)) {
            assertFalse(state.update(floatArrayOf(0f, -9f, 0f), stamp, 2_020_000_000L))
            assertArrayEquals(fresh, state.sample(), 0f)
        }
        assertFalse(state.update(fresh, 3_000_000_000L, 3_250_000_001L))
    }

    @Test fun stalled_sensor_expires_even_when_ui_keeps_ticking() {
        val state = LinearAccelerationState()
        assertTrue(state.update(floatArrayOf(0f, 3f, 0f), 1_000_000_000L, 1_010_000_000L))
        state.expire(1_250_000_000L)
        assertTrue(state.valid)
        state.expire(1_250_000_001L)
        assertFalse(state.valid)
        assertArrayEquals(FloatArray(3), state.sample(), 0f)
    }

    @Test fun nonfinite_or_short_events_never_become_valid_measurements() {
        val state = LinearAccelerationState()
        for (sample in listOf(floatArrayOf(0f, Float.NaN, 0f), floatArrayOf(Float.POSITIVE_INFINITY, 0f, 0f), floatArrayOf(0f, 0f))) {
            assertFalse(state.update(sample, 1_000_000_000L, 1_010_000_000L))
            assertFalse(state.valid)
        }
    }

    @Test fun clear_and_monotonic_clock_regression_remove_the_acceleration() {
        val state = LinearAccelerationState()
        assertTrue(state.update(floatArrayOf(0f, 3f, 0f), 1_000_000_000L, 1_010_000_000L))
        state.clear()
        assertFalse(state.valid)
        assertArrayEquals(FloatArray(3), state.sample(), 0f)
        assertTrue(state.update(floatArrayOf(0f, -3f, 0f), 2_000_000_000L, 2_010_000_000L))
        state.expire(1_999_999_999L)
        assertFalse(state.valid)
    }

    @Test fun timestamped_launch_cruise_brake_fixture_has_no_estimator_delay_or_axis_conversion() {
        val state = LinearAccelerationState()
        val fixture = listOf(0f, 0f, 1f, 2f, 3f, 3f, 1f, 0f, 0f, -1f, -3f, 0f)
        fixture.forEachIndexed { index, y ->
            val stamp = 1_000_000_000L + index * 20_000_000L
            assertTrue(state.update(floatArrayOf(0f, y, 0f), stamp, stamp + 1_000_000L))
            assertEquals(y, state.sample()[1], 0f)
        }
    }
}
