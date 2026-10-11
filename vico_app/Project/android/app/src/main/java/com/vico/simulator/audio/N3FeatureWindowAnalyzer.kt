package com.vico.simulator.audio

import kotlin.math.PI
import kotlin.math.sqrt
import kotlin.math.sin

/** Bounded diagnostic measurements only. No qualification, tuning or gain optimization. */
class N3FeatureWindowAnalyzer {
    data class Result(
        val rms: Double,
        val zeroCrossings: Int,
        val lowBandEnergy: Double,
        val highBandEnergy: Double,
        val periodicity: Double,
    )

    fun analyze(pcm: FloatArray): Result {
        require(pcm.isNotEmpty())
        require(pcm.all { it.isFinite() })
        val rms = sqrt(pcm.fold(0.0) { sum, value -> sum + value * value } / pcm.size)
        var crossings = 0
        for (i in 1 until pcm.size) {
            if ((pcm[i - 1] < 0f) != (pcm[i] < 0f)) crossings++
        }
        val low = bandEnergy(pcm, 1, 8)
        val high = bandEnergy(pcm, 8, 32)
        val periodicity = if (pcm.size < 2) 0.0 else {
            var correlation = 0.0
            for (i in 1 until pcm.size) correlation += pcm[i].toDouble() * pcm[i - 1]
            correlation / pcm.size
        }
        return Result(rms, crossings, low, high, periodicity)
    }

    private fun bandEnergy(samples: FloatArray, start: Int, end: Int): Double {
        var total = 0.0
        for (bin in start until end) {
            var re = 0.0
            var im = 0.0
            samples.forEachIndexed { index, value ->
                val angle = 2.0 * PI * bin * index / samples.size
                re += value * kotlin.math.cos(angle)
                im -= value * kotlin.math.sin(angle)
            }
            total += re * re + im * im
        }
        return total / samples.size
    }
}
