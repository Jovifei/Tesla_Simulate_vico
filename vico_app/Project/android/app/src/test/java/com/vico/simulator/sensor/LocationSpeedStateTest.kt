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

    @Test
    fun delayed_older_fix_cannot_rewind_a_newer_speed() {
        val state = LocationSpeedState()
        assertTrue(state.update(20.0, true, 2_000_000_000L, 2_100_000_000L))
        assertFalse(state.update(10.0, true, 1_500_000_000L, 2_200_000_000L))
        assertEquals(72.0, state.speedKmh, 1e-9)
    }

    @Test
    fun duplicate_timestamp_cannot_replace_current_speed() {
        val state = LocationSpeedState()
        assertTrue(state.update(20.0, true, 2_000_000_000L, 2_100_000_000L))
        assertFalse(state.update(5.0, true, 2_000_000_000L, 2_200_000_000L))
        assertEquals(72.0, state.speedKmh, 1e-9)
    }

    @Test
    fun nonfinite_speeds_are_not_measurements() {
        for (speed in listOf(Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY, Double.MAX_VALUE)) {
            val state = LocationSpeedState()
            assertFalse("Invalid speed $speed", state.update(speed, true, 2_000_000_000L, 2_100_000_000L))
            assertFalse(state.gpsOk)
            assertEquals(0.0, state.speedKmh, 0.0)
        }
    }

    @Test
    fun rejection_does_not_extend_the_last_valid_fix_lifetime() {
        val state = LocationSpeedState()
        assertTrue(state.update(20.0, true, 2_000_000_000L, 2_100_000_000L))
        assertFalse(state.update(5.0, true, 1_000_000_000L, 3_500_000_000L))
        state.expire(5_000_000_001L)
        assertFalse(state.gpsOk)
    }

    @Test
    fun loss_of_monotonic_clock_validity_clears_the_measurement() {
        val state = LocationSpeedState()
        assertTrue(state.update(20.0, true, 2_000_000_000L, 2_100_000_000L))
        state.expire(1_999_999_999L)
        assertFalse(state.gpsOk)
        assertEquals(0.0, state.speedKmh, 0.0)
    }

    @Test
    fun timestamped_ramp_preserves_latest_measurement_without_smoothing_delay() {
        val state = LocationSpeedState()
        for (index in 0..20) {
            val stamp = 1_000_000_000L + index * 100_000_000L
            val speedMps = index * 0.2
            assertTrue(state.update(speedMps, true, stamp, stamp + 10_000_000L))
            assertEquals(speedMps * 3.6, state.speedKmh, 1e-9)
        }
    }

    @Test
    fun batch_selects_newest_usable_fix_even_if_later_entries_are_invalid() {
        val state = LocationSpeedState()
        val now = 4_000_000_000L
        assertTrue(state.updateLatest(listOf(
            LocationSpeedSample(10.0, true, 3_500_000_000L),
            LocationSpeedSample(11.0, true, 3_600_000_000L),
            LocationSpeedSample(0.0, false, 3_700_000_000L),
            LocationSpeedSample(Double.NaN, true, 3_800_000_000L),
            LocationSpeedSample(50.0, true, 4_100_000_000L),
        ), now))
        assertEquals(39.6, state.speedKmh, 1e-9)
        assertFalse(state.updateLatest(listOf(LocationSpeedSample(9.0, true, 3_550_000_000L)), now))
        assertEquals(39.6, state.speedKmh, 1e-9)
    }

    @Test
    fun empty_or_entirely_invalid_batch_preserves_last_valid_speed() {
        val state = LocationSpeedState()
        assertTrue(state.update(20.0, true, 2_000_000_000L, 2_100_000_000L))
        assertFalse(state.updateLatest(emptyList(), 2_200_000_000L))
        assertFalse(state.updateLatest(listOf(LocationSpeedSample(1.0, false, 2_100_000_000L)), 2_200_000_000L))
        assertEquals(72.0, state.speedKmh, 1e-9)
    }
}
