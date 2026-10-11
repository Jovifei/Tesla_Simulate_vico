package com.vico.simulator.audio

import com.vico.simulator.sound.S13PcmCaptureReport
import com.vico.simulator.sound.S13ReviewContract
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AcousticFeatureExtractorFixtureTest {
    @Test
    fun finiteFixtureWithoutIndependentReferenceIsNotEvaluated() {
        val extractor = AcousticFeatureExtractor()
        val pcm = FloatArray(S13ReviewContract.TOTAL_FRAMES)
        pcm[0] = 1f
        val capture = S13PcmCaptureReport(
            requestedFrames = S13ReviewContract.TOTAL_FRAMES.toLong(),
            acceptedFrames = S13ReviewContract.TOTAL_FRAMES.toLong(),
            capturedFrames = S13ReviewContract.TOTAL_FRAMES,
            capacityFrames = S13ReviewContract.TOTAL_FRAMES,
            overflow = false,
            failed = false,
            sha256 = "a".repeat(64),
        )
        val result = extractor.extract(
            pcm,
            capture,
            null,
        )
        assertEquals("NOT_EVALUATED/missing_reference", result.referenceState)
        assertTrue(result.rms.isFinite())
    }
}
