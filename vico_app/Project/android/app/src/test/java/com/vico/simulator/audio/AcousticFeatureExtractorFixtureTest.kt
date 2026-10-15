package com.vico.simulator.audio

import com.vico.simulator.sound.S13CaptureBinding
import com.vico.simulator.sound.S13PcmCaptureReport
import com.vico.simulator.sound.S13ReviewContract
import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

class AcousticFeatureExtractorFixtureTest {
    private fun actualHash(pcm: FloatArray): String {
        val bytes = ByteBuffer.allocate(pcm.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        pcm.forEach { bytes.putFloat(it) }
        return MessageDigest.getInstance("SHA-256").digest(bytes.array())
            .joinToString("") { "%02x".format(it.toInt() and 255) }
    }

    private fun receipt(pcm: FloatArray) = S13PcmCaptureReport(
        requestedFrames = S13ReviewContract.TOTAL_FRAMES.toLong(),
        acceptedFrames = S13ReviewContract.TOTAL_FRAMES.toLong(),
        capturedFrames = S13ReviewContract.TOTAL_FRAMES,
        capacityFrames = S13ReviewContract.TOTAL_FRAMES,
        overflow = false, failed = false, sha256 = actualHash(pcm),
    )

    @Test fun actualFiniteFixtureWithoutReferenceRemainsNotEvaluated() {
        val pcm = FloatArray(S13ReviewContract.TOTAL_FRAMES)
        pcm[0] = 1f
        val capture = receipt(pcm).copy(binding = S13CaptureBinding(
            "vehicle\"key", "source", "trace", "bank", "schedule"))
        val result = AcousticFeatureExtractor().extract(pcm, capture)
        assertEquals("NOT_EVALUATED/missing_reference", result.referenceState)
        assertEquals(capture.sha256, result.sha256)
        assertEquals(capture.binding, result.captureBinding)
        assertEquals(pcm.size, result.samples)
        assertEquals(1.0 / pcm.size, result.rms * result.rms, 1e-12)
        val json = result.toJson()
        assertTrue(json.contains("\"comparison_errors\":null"))
        assertTrue(json.contains("vehicle\\\"key"))
        assertTrue(json.contains("\"pcm_sha256\":\"${capture.sha256}\""))
        assertTrue(json.contains("NOT_EVALUATED/no_time_aligned_rpm_state"))
    }

    @Test fun alignmentBooleanAndMetadataCannotProduceReferenceQualification() {
        val pcm = FloatArray(S13ReviewContract.TOTAL_FRAMES)
        val capture = receipt(pcm)
        val reference = AcousticFeatureExtractor.ArtifactIdentity(
            capture.sha256, 48000, 1, capture.captureDomain, independentlyAligned = true)
        val result = AcousticFeatureExtractor().extract(pcm, capture, reference)
        assertEquals("NOT_EVALUATED/reference_pcm_comparison_not_implemented", result.referenceState)
        assertEquals("MEASURED_FEATURE_ONLY", result.evaluation)
        assertEquals(null, result.features.lagOneCorrelation)
        assertTrue(result.toJson().contains("\"crest_factor\":null"))
    }

    @Test fun validatorRejectsFalseReceiptsAndCorruptedSamples() {
        val pcm = FloatArray(S13ReviewContract.TOTAL_FRAMES)
        val report = receipt(pcm)
        assertTrue(PcmArtifactHashValidator.validate(report, pcm).isSuccess)
        val invalid = listOf(report.copy(sha256 = "a".repeat(64)), report.copy(sha256 = "bad"),
            report.copy(requestedFrames = report.requestedFrames - 1),
            report.copy(acceptedFrames = report.acceptedFrames - 1),
            report.copy(capturedFrames = report.capturedFrames - 1),
            report.copy(capacityFrames = report.capacityFrames - 1),
            report.copy(overflow = true), report.copy(failed = true),
            report.copy(captureDomain = "UNKNOWN"))
        invalid.forEach { assertTrue(PcmArtifactHashValidator.validate(it, pcm).isFailure) }
        assertTrue(PcmArtifactHashValidator.validate(report, pcm.copyOf(pcm.size - 1)).isFailure)
        pcm[17] = Float.NaN
        assertTrue(PcmArtifactHashValidator.validate(report, pcm).isFailure)
        pcm[17] = Float.POSITIVE_INFINITY
        assertTrue(PcmArtifactHashValidator.validate(report, pcm).isFailure)
        pcm[17] = 0.1f
        assertThrows(IllegalArgumentException::class.java) { AcousticFeatureExtractor().extract(pcm, report) }
    }

    @Test fun hashMatchesActualLittleEndianBytesIncludingNegativeZeroAndChunkTail() {
        val pcm = FloatArray(1025) { when (it % 4) { 0 -> 1f; 1 -> -0.0f; 2 -> -0.5f; else -> 0.25f } }
        assertEquals(actualHash(pcm), PcmArtifactHashValidator.sha256F32le(pcm))
        pcm[1] = 0f
        assertEquals(actualHash(pcm), PcmArtifactHashValidator.sha256F32le(pcm))
        assertThrows(IllegalArgumentException::class.java) { PcmArtifactHashValidator.sha256F32le(FloatArray(0)) }
        assertThrows(IllegalArgumentException::class.java) {
            PcmArtifactHashValidator.sha256F32le(FloatArray(N3FeatureWindowAnalyzer.HARD_MAX_SAMPLES + 1))
        }
    }

    @Test fun allSupportedDomainsValidateWithoutEquatingTheirIdentity() {
        val pcm = FloatArray(S13ReviewContract.TOTAL_FRAMES)
        val capture = receipt(pcm)
        listOf("POST_ENVELOPES_PRE_AUDIOTRACK_ACCEPTED", "POST_ENVELOPES_PRE_AUDIOTRACK_SUBMISSION",
            "S14_REFERENCE_PRE_AUDIOTRACK_SUBMISSION").forEach { domain ->
            assertTrue(PcmArtifactHashValidator.validate(capture.copy(captureDomain = domain), pcm).isSuccess)
        }
    }

    @Test fun captureSchemaAndAlgorithmBoundsAreFixed() {
        assertThrows(IllegalArgumentException::class.java) { AcousticFeatureExtractor(sampleRateHz = 96000) }
        assertThrows(IllegalArgumentException::class.java) { AcousticFeatureExtractor(algorithmVersion = "n3-rms-v4") }
        assertThrows(IllegalArgumentException::class.java) { AcousticFeatureExtractor(maxSamples = Int.MAX_VALUE) }
    }
}
