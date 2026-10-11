package com.vico.simulator.audio

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** Bounded diagnostic measurements only. No qualification, tuning or gain optimization. */
class N3FeatureWindowAnalyzer(
    private val sampleRateHz: Int = 48000,
    private val maxSamples: Int = 48000 * 10,
) {
    data class Result(
        val rms: Double,
        val zeroCrossings: Int,
        val lowBandEnergy: Double,
        val highBandEnergy: Double,
        val periodicity: Double,
        val normalization: String = "MEAN_SQUARE_DIVIDED_BY_SAMPLE_COUNT",
    )

    fun analyze(pcm: FloatArray): Result {
        require(pcm.isNotEmpty() && pcm.size <= maxSamples)
        require(pcm.all { it.isFinite() })
        val rms = sqrt(pcm.fold(0.0) { sum, value -> sum + value.toDouble() * value.toDouble() } / pcm.size)
        var crossings = 0
        for (i in 1 until pcm.size) if ((pcm[i - 1] < 0f) != (pcm[i] < 0f)) crossings++
        return Result(rms, crossings, bandEnergy(pcm, 0.0, 500.0), bandEnergy(pcm, 2000.0, 8000.0), lagOne(pcm))
    }

    private fun bandEnergy(samples: FloatArray, lowHz: Double, highHz: Double): Double {
        var total = 0.0
        val start = (lowHz * samples.size / sampleRateHz).toInt()
        val end = (highHz * samples.size / sampleRateHz).toInt().coerceAtLeast(start + 1)
        for (bin in start until end) {
            var re = 0.0
            var im = 0.0
            samples.forEachIndexed { index, value ->
                val angle = 2.0 * PI * bin * index / samples.size
                re += value * cos(angle)
                im -= value * sin(angle)
            }
            total += re * re + im * im
        }
        return total / samples.size
    }

    private fun lagOne(samples: FloatArray): Double {
        var sum = 0.0
        for (i in 1 until samples.size) sum += samples[i].toDouble() * samples[i - 1]
        return sum / samples.size
    }
}
