package com.vico.simulator.audio

import kotlin.math.sqrt

/** Bounded diagnostic measurements only. No qualification, tuning or gain optimization. */
class N3FeatureWindowAnalyzer(
    private val sampleRateHz: Int = 48000,
    private val maxSamples: Int = 48000 * 10,
    private val frameSize: Int = 2048,
    private val hopSize: Int = 1024,
) {
    data class Result(
        val rms: Double,
        val zeroCrossings: Int,
        val lowBandEnergy: Double,
        val highBandEnergy: Double,
        val periodicity: Double,
        val normalization: String = "ONE_SIDED_PARSEVAL_MEAN_SQUARE",
    )

    fun analyze(pcm: FloatArray): Result {
        require(pcm.isNotEmpty() && pcm.size <= maxSamples)
        require(pcm.all { it.isFinite() })
        require(frameSize > 0 && hopSize > 0)
        val rms = sqrt(pcm.fold(0.0) { sum, value -> sum + value.toDouble() * value.toDouble() } / pcm.size)
        var crossings = 0
        for (i in 1 until pcm.size) if ((pcm[i - 1] < 0f) != (pcm[i] < 0f)) crossings++
        var low = 0.0
        var high = 0.0
        var frames = 0
        var start = 0
        while (start + frameSize <= pcm.size) {
            val powers = spectrumFrame(pcm, start)
            low += powers.first
            high += powers.second
            frames++
            start += hopSize
        }
        val scale = if (frames == 0) 1.0 else frames.toDouble()
        return Result(rms, crossings, low / scale, high / scale, lagOne(pcm))
    }

    private fun spectrumFrame(samples: FloatArray, offset: Int): Pair<Double, Double> {
        var low = 0.0
        var high = 0.0
        val bins = frameSize / 2 + 1
        for (bin in 0 until bins) {
            var re = 0.0
            var im = 0.0
            for (i in 0 until frameSize) {
                val x = samples[offset + i].toDouble()
                val angle = 2.0 * Math.PI * bin * i / frameSize
                re += x * kotlin.math.cos(angle)
                im -= x * kotlin.math.sin(angle)
            }
            val hz = bin.toDouble() * sampleRateHz / frameSize
            val energy = (re * re + im * im) / frameSize
            if (hz <= 500.0) low += energy else if (hz in 2000.0..8000.0) high += energy
        }
        return low to high
    }

    private fun lagOne(samples: FloatArray): Double {
        var sum = 0.0
        for (i in 1 until samples.size) sum += samples[i].toDouble() * samples[i - 1]
        return sum / samples.size
    }
}
