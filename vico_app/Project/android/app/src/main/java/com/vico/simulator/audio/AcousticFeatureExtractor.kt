package com.vico.simulator.audio

import com.vico.simulator.sound.S13PcmCaptureReport
import kotlin.math.sqrt

/** Bounded PCM feature extraction. Measurements only; no gain/DSP tuning. */
class AcousticFeatureExtractor(
    private val sampleRateHz: Int = 48000,
    private val algorithmVersion: String = "n3-rms-v4",
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
        require(capture.captureDomain == "POST_ENVELOPES_PRE_AUDIOTRACK_ACCEPTED") { "unsupported capture domain" }
        PcmArtifactHashValidator.validate(capture, pcm).getOrThrow()
        require(pcm.size <= maxSamples) { "pcm exceeds bounded extraction window" }
        val rms = sqrt(pcm.fold(0.0) { acc, value -> acc + value.toDouble() * value.toDouble() } / pcm.size)
        val referenceState = when {
            reference == null -> "NOT_EVALUATED/missing_reference"
            reference.sha256 == capture.sha256 -> "NOT_EVALUATED/non_independent_reference"
            else -> "REFERENCE_BOUND"
        }
        return Result(algorithmVersion, pcm.size, rms, "MEASURED_FEATURE_ONLY", referenceState)
    }
}
