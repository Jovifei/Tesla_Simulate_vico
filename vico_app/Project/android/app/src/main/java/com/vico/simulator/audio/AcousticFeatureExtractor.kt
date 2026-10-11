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
        val independentlyAligned: Boolean = false,
    )

    data class Result(
        val algorithm: String,
        val samples: Int,
        val rms: Double,
        val evaluation: String,
        val referenceState: String,
    )

    fun extract(pcm: FloatArray, capture: S13PcmCaptureReport, reference: ArtifactIdentity? = null): Result {
        require(sampleRateHz == 48000 || sampleRateHz == 96000) { "unsupported sample rate" }
        require(algorithmVersion == "n3-rms-v4") { "unsupported algorithm" }
        PcmArtifactHashValidator.validate(capture, pcm).getOrThrow()
        require(pcm.size <= maxSamples) { "pcm exceeds bounded extraction window" }
        val rms = sqrt(pcm.fold(0.0) { acc, value -> acc + value.toDouble() * value.toDouble() } / pcm.size)
        val referenceState = when {
            reference == null -> "NOT_EVALUATED/missing_reference"
            !reference.independentlyAligned -> "NOT_EVALUATED/reference_not_independently_aligned"
            reference.sampleRateHz != sampleRateHz || reference.channels != 1 -> "NOT_EVALUATED/reference_format_mismatch"
            else -> "REFERENCE_BOUND"
        }
        return Result(algorithmVersion, pcm.size, rms, "MEASURED_FEATURE_ONLY", referenceState)
    }
}
