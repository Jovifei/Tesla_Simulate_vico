package com.vico.simulator.sensor

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CalibrationAccumulatorTest {

    @Test
    fun completes_with_independent_xyz_offsets_and_corrects_the_next_sample() {
        val accumulator = CalibrationAccumulator(requiredSamples = 3)

        accumulator.add(floatArrayOf(0.12f, -0.21f, 0.08f))
        accumulator.add(floatArrayOf(0.10f, -0.19f, 0.10f))
        assertFalse(accumulator.isReady)
        accumulator.add(floatArrayOf(0.11f, -0.20f, 0.09f))

        assertTrue(accumulator.isReady)
        assertArrayEquals(floatArrayOf(0.11f, -0.20f, 0.09f), accumulator.offsets(), 0.0001f)
        assertArrayEquals(floatArrayOf(0.09f, 0.10f, -0.04f), accumulator.correct(floatArrayOf(0.20f, -0.10f, 0.05f)), 0.0001f)
    }
}
