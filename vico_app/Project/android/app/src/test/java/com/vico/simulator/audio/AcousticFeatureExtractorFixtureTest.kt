package com.vico.simulator.audio

import com.vico.simulator.sound.S13PcmCaptureReport
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AcousticFeatureExtractorFixtureTest {
    @Test
    fun finiteFixtureWithoutIndependentReferenceIsNotEvaluated() {
        val extractor = AcousticFeatureExtractor()
        val capture = S13PcmCaptureReport(
            requestedFrames = 4,
            acceptedFrames = 4,
            capturedFrames = 4,
            capacityFrames = 4,
            overflow = false,
            failed = false,
            sha256 = "a".repeat(64),
        )
        val result = extractor.extract(
            floatArrayOf(0f, 1f, 0f, -1f),
            capture,
            null,
        )
        assertEquals("NOT_EVALUATED", result.referenceState)
        assertTrue(result.finite)
    }
}
