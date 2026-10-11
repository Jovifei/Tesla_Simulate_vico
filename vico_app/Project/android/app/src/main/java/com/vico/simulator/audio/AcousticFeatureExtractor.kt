package com.vico.simulator.audio

import kotlin.math.sqrt

/**
 * Bounded PCM feature extraction. Measurements only; never tunes DSP/gain or
 * claims independent acoustic qualification without a reference artifact.
 */
class AcousticFeatureExtractor(
    private val sampleRateHz: Int = 48000,
    private val algorithmVersion: String = "n3-rms-v2",
    private val maxSamples: Int = 48000 * 30,
) {
    data class ArtifactIdentity(
        val source: String,
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

    fun extract(pcm: FloatArray, artifact: ArtifactIdentity, reference: ArtifactIdentity? = null): Result {
        require(algorithmVersion == "n3-rms-v2") { "unsupported algorithm" }
        require(sampleRateHz == artifact.sampleRateHz) { "artifact sample rate mismatch" }
        require(artifact.channels == 1) { "only mono artifacts supported" }
        require(artifact.sha256.isNotBlank()) { "artifact identity missing" }
        require(pcm.isNotEmpty() && pcm.size <= maxSamples) { "pcm outside bounded window" }
        if (pcm.any { !it.isFinite() }) {
            return Result(algorithmVersion, pcm.size, 0.0, false, "REJECT_NONFINITE", "NOT_EVALUATED")
        }
        val rms = sqrt(pcm.fold(0.0) { a, v -> a + v.toDouble() * v.toDouble() } / pcm.size)
        return Result(
            algorithmVersion,
            pcm.size,
            rms,
            true,
            "MEASURED_FEATURE_ONLY",
            if (reference?.sha256?.isNotBlank() == true) "REFERENCE_BOUND" else "NOT_EVALUATED",
        )
    }
}
