package com.vico.simulator.audio

import com.vico.simulator.sound.S13PcmCaptureReport
import kotlin.math.sqrt

/**
 * Bounded PCM feature extraction. Measurements only; no gain/DSP tuning and no
 * acoustic qualification without an independently aligned reference artifact.
 */
class AcousticFeatureExtractor(
    private val sampleRateHz: Int = 48000,
    private val algorithmVersion: String = "n3-rms-v3",
    private val maxSamples: Int = 48000 * 30,
) {
    data class ArtifactIdentity(
        val sha256: String,
        val sampleRateHz: Int,
        val channels: Int,
        val captureDomain: String,
    )

    data class Result(
        val algorithm: String,
        val samples: Int,
        val rms: Double,
        val evaluation: String,
        val referenceState: String,
    )

    fun extract(
        pcm: FloatArray,
        capture: S13PcmCaptureReport,
        reference: ArtifactIdentity? = null,
    ): Result {
        require(algorithmVersion == "n3-rms-v3") { "unsupported algorithm" }
        require(capture.sha256.isNotBlank()) { "capture hash missing" }
        require(capture.captureDomain == "POST_ENVELOPES_PRE_AUDIOTRACK_ACCEPTED") { "unsupported capture domain" }
        require(capture.fullWindow) { "capture window incomplete" }
        require(pcm.isNotEmpty() && pcm.size == capture.capturedFrames) { "pcm/capture size mismatch" }
        require(pcm.size <= maxSamples) { "pcm exceeds bounded extraction window" }
        require(pcm.all { it.isFinite() }) { "non-finite pcm" }

        val artifact = ArtifactIdentity(
            sha256 = capture.sha256,
            sampleRateHz = sampleRateHz,
            channels = 1,
            captureDomain = capture.captureDomain,
        )
        require(artifact.sampleRateHz == sampleRateHz)
        require(artifact.channels == 1)

        val rms = sqrt(pcm.fold(0.0) { acc, value ->
            acc + value.toDouble() * value.toDouble()
        } / pcm.size)

        val referenceState = when {
            reference == null -> "NOT_EVALUATED/missing_reference"
            reference.sha256 == artifact.sha256 -> "NOT_EVALUATED/non_independent_reference"
            reference.sampleRateHz != artifact.sampleRateHz || reference.channels != artifact.channels ->
                "NOT_EVALUATED/reference_format_mismatch"
            else -> "REFERENCE_BOUND"
        }

        return Result(
            algorithm = algorithmVersion,
            samples = pcm.size,
            rms = rms,
            evaluation = "MEASURED_FEATURE_ONLY",
            referenceState = referenceState,
        )
    }
}
