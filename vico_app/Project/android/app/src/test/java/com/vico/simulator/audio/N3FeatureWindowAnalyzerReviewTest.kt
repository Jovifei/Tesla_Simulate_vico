package com.vico.simulator.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertThrows
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

/** Analytic, bin-aligned signals verify the advertised mean-square energy domain. */
class N3FeatureWindowAnalyzerReviewTest {
    @Test fun lowToneHasHalfUnitMeanSquareEnergy() {
        val pcm = FloatArray(2048) { sin(2.0 * PI * 4 * it / 2048).toFloat() }
        val result = N3FeatureWindowAnalyzer().analyze(pcm)
        assertEquals(0.5, result.rms * result.rms, 1e-6)
        assertEquals(0.5, result.lowBandEnergy, 1e-6)
        assertEquals(0.0, result.highBandEnergy, 1e-6)
    }

    @Test fun highToneHasHalfUnitMeanSquareEnergy() {
        val pcm = FloatArray(2048) { sin(2.0 * PI * 128 * it / 2048).toFloat() }
        val result = N3FeatureWindowAnalyzer().analyze(pcm)
        assertEquals(0.0, result.lowBandEnergy, 1e-6)
        assertEquals(0.5, result.highBandEnergy, 1e-6)
    }

    @Test fun dcAndNyquistAreNotDoubled() {
        val dc = N3FeatureWindowAnalyzer().analyze(FloatArray(2048) { 0.25f })
        assertEquals(0.0625, dc.lowBandEnergy, 1e-9)
        assertEquals(0.0625, dc.spectralMeanSquare, 1e-9)
        val nyquist = N3FeatureWindowAnalyzer().analyze(FloatArray(2048) { if (it % 2 == 0) 1f else -1f })
        assertEquals(1.0, nyquist.spectralMeanSquare, 1e-9)
        assertEquals(-1.0, nyquist.lagOneCorrelation!!, 1e-9)
    }

    @Test fun amplitudeScalesEnergyQuadraticallyAndFramesAreAveraged() {
        val pcm = FloatArray(4096) { (0.25 * sin(2.0 * PI * 128 * it / 2048)).toFloat() }
        val result = N3FeatureWindowAnalyzer().analyze(pcm)
        assertEquals(3, result.spectrumFrames)
        assertEquals(0.03125, result.highBandEnergy, 1e-8)
        assertEquals(result.rms * result.rms, result.spectralMeanSquare, 1e-8)
        assertEquals(0.25, result.peakAbsolute, 1e-8)
        assertEquals(kotlin.math.sqrt(2.0), result.crestFactor!!, 1e-6)
    }

    @Test fun silenceHasNoInventedCorrelationOrCrest() {
        val result = N3FeatureWindowAnalyzer().analyze(FloatArray(2048))
        assertEquals(0.0, result.rms, 0.0)
        assertEquals(0.0, result.spectralMeanSquare, 0.0)
        assertEquals(null, result.lagOneCorrelation)
        assertEquals(null, result.crestFactor)
    }

    @Test fun parsevalMatchesImpulseAndMixedSignalAtBothSampleRates() {
        val impulse = FloatArray(2048).also { it[777] = 1f }
        val impulseResult = N3FeatureWindowAnalyzer().analyze(impulse)
        assertEquals(1.0 / 2048, impulseResult.spectralMeanSquare, 1e-12)
        assertEquals(1.0, impulseResult.maxAdjacentStep, 0.0)
        val mixed = FloatArray(4096) {
            (0.125 + 0.5 * sin(2.0 * PI * 128 * it / 4096) +
                0.25 * sin(2.0 * PI * 2 * it / 4096)).toFloat()
        }
        val result = N3FeatureWindowAnalyzer(sampleRateHz = 96000, frameSize = 4096, hopSize = 4096).analyze(mixed)
        assertEquals(0.125 * 0.125 + 0.25 * 0.25 / 2, result.lowBandEnergy, 1e-7)
        assertEquals(0.5 * 0.5 / 2, result.highBandEnergy, 1e-7)
        assertEquals(result.rms * result.rms, result.spectralMeanSquare, 1e-7)
    }

    @Test fun partialTailIsDeclaredAndWholeCaptureRmsIncludesIt() {
        val pcm = FloatArray(2049).also { it[2048] = 1f }
        val result = N3FeatureWindowAnalyzer().analyze(pcm)
        assertEquals(1, result.spectrumFrames)
        assertEquals(2048, result.spectrumCoveredSamples)
        assertEquals(1, result.trailingSamples)
        assertEquals(0.0, result.spectralMeanSquare, 0.0)
        assertEquals(1.0 / 2049, result.rms * result.rms, 1e-12)
    }

    @Test fun rejectUnboundedAndMalformedConfigurationBeforeWork() {
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer(sampleRateHz = 0) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer(maxSamples = Int.MAX_VALUE) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer(frameSize = 8192) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer(frameSize = 1000) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer(hopSize = 1) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer(hopSize = Int.MAX_VALUE) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer().analyze(FloatArray(2047)) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer().analyze(FloatArray(2048) { Float.NaN }) }
        assertThrows(IllegalArgumentException::class.java) { N3FeatureWindowAnalyzer().analyze(FloatArray(2048) { Float.POSITIVE_INFINITY }) }
        val bounded = N3FeatureWindowAnalyzer(sampleRateHz = 96000, frameSize = 4096, hopSize = 4096)
        assertTrue(bounded.analyze(FloatArray(4096)).spectralMeanSquare.isFinite())
    }
}
