package com.vico.simulator.audio

import kotlin.math.sqrt

/**
 * Deterministic PCM feature extraction foundation.
 * It reports measurements only; it does not tune gain, DSP, or declare acoustic
 * qualification without an independent reference.
 */
class AcousticFeatureExtractor(
    private val sampleRateHz: Int = 48000,
    private val algorithmVersion: String = "n3-rms-v1",
) {
    data class Result(
        val algorithm: String,
        val samples: Int,
        val rms: Double,
        val finite: Boolean,
        val evaluation: String,
    )

    fun extract(pcm: FloatArray): Result {
        require(sampleRateHz > 0) { "invalid sample rate" }
        require(pcm.isNotEmpty()) { "empty pcm" }
        val finite = pcm.all { it.isFinite() }
        if (!finite) {
            return Result(algorithmVersion, pcm.size, Double.NaN, false, "REJECT_NONFINITE")
        }
        val meanSquare = pcm.fold(0.0) { acc, value ->
            acc + value.toDouble() * value.toDouble()
        } / pcm.size
        return Result(
            algorithm = algorithmVersion,
            samples = pcm.size,
            rms = sqrt(meanSquare),
            finite = true,
            evaluation = "MEASURED_FEATURE_ONLY",
        )
    }
}
