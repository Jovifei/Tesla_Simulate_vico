package com.vico.simulator.audio

import com.vico.simulator.sound.S13CaptureBinding
import com.vico.simulator.sound.S13PcmCaptureReport
import com.vico.simulator.sound.S13ReviewContract
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

class AcousticReferenceComparatorTest {
    private val comparator = AcousticReferenceComparator()
    private val alignment = AcousticReferenceComparator.Alignment(true, "independent-fixture-clock-v1")
    private fun tone(low: Double = .2, high: Double = .1, size: Int = 4096) = FloatArray(size) {
        (low * sin(2 * PI * 375 * it / 48000) + high * sin(2 * PI * 3000 * it / 48000)).toFloat()
    }
    private fun identity(pcm: FloatArray) = AcousticReferenceComparator.PcmIdentity(
        PcmArtifactHashValidator.sha256F32le(pcm), 48000, 1, "f32le",
        PcmArtifactHashValidator.CAPTURE_DOMAIN, "hellcat_v6")

    @Test fun extractorOffersExplicitActualReferencePcmComparison() {
        assertTrue("Actual reference PCM comparison API is missing",
            AcousticFeatureExtractor::class.java.methods.any { it.name == "compareWithReference" })
    }

    @Test fun identicalActualPcmHasFiniteZeroDeltasWithoutOemQualification() {
        val pcm = tone()
        val result = comparator.compare(pcm, identity(pcm), pcm.copyOf(), identity(pcm), alignment)
        assertEquals("MEASURED_RELATIVE_COMPARISON", result.evaluation)
        val d = requireNotNull(result.differences)
        listOf(d.rms, d.rmsDb, d.lowBandEnergyRatio, d.highBandEnergyRatio,
            d.crestFactor, d.spectralMeanSquare).forEach { assertEquals(0.0, it, 0.0) }
        assertEquals("CALLER_DECLARED_NOT_AUTOMATICALLY_VERIFIED", result.alignmentState)
        assertEquals(result.toJson(), result.toJson())
        assertTrue(result.toJson().contains("\"comparison_errors\":{"))
        assertFalse(result.toJson().contains("similarity_percent"))
        assertTrue(result.toJson().contains("NOT_EVALUATED/no_time_aligned_rpm_state"))
    }

    @Test fun spectralBalanceChangesAreDetectedWithoutGainNormalization() {
        val capture = tone(.4, .1)
        val reference = tone(.1, .4)
        val d = requireNotNull(comparator.compare(capture, identity(capture), reference,
            identity(reference), alignment).differences)
        assertTrue(d.lowBandEnergyRatio > .8)
        assertTrue(d.highBandEnergyRatio < -.8)
        assertEquals(0.0, d.rmsDb, 1e-6)
        val quiet = tone(.2, .05)
        val gain = requireNotNull(comparator.compare(capture, identity(capture), quiet,
            identity(quiet), alignment).differences)
        assertEquals(6.020599913, gain.rmsDb, 1e-6)
        assertTrue(gain.spectralMeanSquare > 0)
    }

    @Test fun missingReferenceOrAlignmentNeverBecomesZeroError() {
        val pcm = tone()
        val id = identity(pcm)
        val missing = comparator.compare(pcm, id, null, null, null)
        assertEquals("missing_reference_pcm_or_identity", missing.reason)
        assertNull(missing.differences)
        assertTrue(missing.toJson().contains("\"comparison_errors\":null"))
        listOf(null, alignment.copy(independentlyAligned = false), alignment.copy(evidenceId = " ")).forEach {
            val result = comparator.compare(pcm, id, pcm, id, it)
            assertEquals("alignment_not_established", result.reason)
            assertNull(result.differences)
        }
    }

    @Test fun differentDomainsVehiclesRatesChannelsFormatsOrLengthsRemainUnevaluated() {
        val pcm = tone()
        val id = identity(pcm)
        val cases = listOf(
            id.copy(captureDomain = "EXTERNAL_MICROPHONE") to "domain_mismatch",
            id.copy(vehicleKey = "ferrari_458") to "vehicle_mismatch",
            id.copy(vehicleKey = "") to "missing_vehicle_identity",
            id.copy(sampleRateHz = 96000) to "sample_rate_mismatch",
            id.copy(channels = 2) to "channel_or_format_mismatch",
            id.copy(format = "s16le") to "channel_or_format_mismatch",
        )
        cases.forEach { (ref, reason) ->
            val result = comparator.compare(pcm, id, pcm, ref, alignment)
            assertEquals(reason, result.reason)
            assertNull(result.differences)
        }
        val short = pcm.copyOf(pcm.size - 1)
        assertEquals("frame_count_mismatch", comparator.compare(pcm, id, short, identity(short), alignment).reason)
    }

    @Test fun corruptedHashNonFiniteAndOversizePcmAreRejected() {
        val pcm = tone()
        val id = identity(pcm)
        assertThrows(IllegalArgumentException::class.java) {
            comparator.compare(pcm, id, pcm, id.copy(sha256 = "a".repeat(64)), alignment)
        }
        assertThrows(IllegalArgumentException::class.java) {
            comparator.compare(pcm, id.copy(sha256 = "bad"), pcm, id, alignment)
        }
        val nan = pcm.copyOf().also { it[30] = Float.NaN }
        assertThrows(IllegalArgumentException::class.java) { comparator.compare(nan, id, pcm, id, alignment) }
        assertThrows(IllegalArgumentException::class.java) { comparator.compare(pcm, id, nan, id, alignment) }
        val large = FloatArray(N3FeatureWindowAnalyzer.HARD_MAX_SAMPLES + 1)
        assertThrows(IllegalArgumentException::class.java) { comparator.compare(large, id, pcm, id, alignment) }
        assertThrows(IllegalArgumentException::class.java) { comparator.compare(pcm, id, large, id, alignment) }
    }

    @Test fun silentCaptureOrReferenceIsNotAQualifiedComparison() {
        val pcm = tone()
        val silent = FloatArray(pcm.size)
        assertEquals("silent_capture_or_reference", comparator.compare(pcm, identity(pcm), silent,
            identity(silent), alignment).reason)
        assertEquals("silent_capture_or_reference", comparator.compare(silent, identity(silent), pcm,
            identity(pcm), alignment).reason)
    }

    @Test fun explicitExtractorApiUsesCaptureReceiptAndBindingWhileOldApiStaysUnassessed() {
        val pcm = tone(size = S13ReviewContract.TOTAL_FRAMES)
        val id = identity(pcm)
        val capture = S13PcmCaptureReport(pcm.size.toLong(), pcm.size.toLong(), pcm.size,
            pcm.size, false, false, id.sha256,
            S13CaptureBinding("hellcat_v6", "source", "trace", "bank", "schedule"))
        val extractor = AcousticFeatureExtractor()
        val actual = extractor.compareWithReference(pcm, capture, pcm, id, alignment)
        assertEquals("MEASURED_RELATIVE_COMPARISON", actual.evaluation)
        assertEquals(0.0, requireNotNull(actual.differences).rms, 0.0)
        val old = extractor.extract(pcm, capture, AcousticFeatureExtractor.ArtifactIdentity(
            id.sha256, 48000, 1, id.captureDomain, true))
        assertEquals("NOT_EVALUATED/reference_pcm_comparison_not_implemented", old.referenceState)
        assertTrue(old.toJson().contains("\"comparison_errors\":null"))
        assertThrows(IllegalArgumentException::class.java) {
            extractor.compareWithReference(pcm, capture.copy(failed = true), pcm, id, alignment)
        }
    }
}
