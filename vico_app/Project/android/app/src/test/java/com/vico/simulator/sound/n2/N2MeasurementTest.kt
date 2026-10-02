package com.vico.simulator.sound.n2

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class N2MeasurementTest {
    @Test
    fun emptyPcmCannotMasqueradeAsEvidence() {
        val result = N2Measurement.measure(floatArrayOf())
        assertFalse(result.finite)
        assertFalse(result.energyFinite)
        assertFalse(result.evidenceValid)
        assertTrue(result.rms.isNaN())
    }

    @Test
    fun squaringPromotesToDoubleBeforeAccumulation() {
        val result = N2Measurement.measure(floatArrayOf(Float.MAX_VALUE, -Float.MAX_VALUE))
        assertTrue(result.finite)
        assertTrue(result.energyFinite)
        assertTrue(result.evidenceValid)
        assertTrue(result.rms.isFinite())
    }

    @Test
    fun nonfinitePcmIsRejected() {
        val result = N2Measurement.measure(floatArrayOf(0.0f, Float.NaN))
        assertFalse(result.finite)
        assertFalse(result.evidenceValid)
    }
}
