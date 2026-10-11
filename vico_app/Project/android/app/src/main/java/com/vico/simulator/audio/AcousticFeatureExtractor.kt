package com.vico.simulator.audio

import com.vico.simulator.sound.S13PcmCaptureReport
import kotlin.math.sqrt

/**
 * Bounded PCM feature extraction over validated capture receipts.
 * Measurement only: no gain/DSP tuning and no acoustic qualification claim.
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
    )

    data class Result(
        val algorithm: String,
        val samples: Int,
        val rms: Double,
        val finite: Boolean,
        val evaluation: String,
        val referenceState: String,
    )

    fun extract(
        pcm: FloatArray,
        capture: S13PcmCaptureReport,
        reference: ArtifactIdentity? = null,
    ): Result {
        require(algorithmVersion == "n3-rms-v3") { "unsupported algorithm" }
        require(capture.sha256.isNotBlank()) { "missing capture artifact" }
        require(capture.fullWindow) { "capture window incomplete" }
        require(capture.captureDomain.isNotBlank()) { "missing capture domain" }
        require(pcm.size <= maxSamples) { "pcm outside bounded window" }
        require(pcm.all { it.isFinite() }) { "non-finite pcm" }
        val rms = sqrt(pcm.fold(0.0) { sum, value -> sum + value.toDouble() * value.toDouble() } / pcm.size)
        val referenceState = when {
            reference == null -> "NOT_EVALUATED/missing_reference"
            reference.sha256 == capture.sha256 -> "REJECT_UNALIGNED_REFERENCE"
            else -> "REFERENCE_BOUND"
        }
        return Result(
            algorithm = algorithmVersion,
            samples = pcm.size,
            rms = rms,
            finite = true,
            evaluation = "MEASURED_FEATURE_ONLY",
            referenceState = referenceState,
        )
    }
}
