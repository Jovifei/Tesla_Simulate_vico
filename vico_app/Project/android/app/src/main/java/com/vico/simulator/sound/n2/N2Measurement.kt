package com.vico.simulator.sound.n2

import kotlin.math.abs
import kotlin.math.sqrt

internal object N2Measurement {
    internal data class Result(
        val sampleCount: Int,
        val finite: Boolean,
        val energyFinite: Boolean,
        val evidenceValid: Boolean,
        val rms: Double,
        val peak: Double,
    )

    fun measure(pcm: FloatArray): Result {
        if (pcm.isEmpty()) {
            return Result(0, false, false, false, Double.NaN, Double.NaN)
        }
        var energy = 0.0
        var peak = 0.0
        for (sample in pcm) {
            if (!sample.isFinite()) {
                return Result(pcm.size, false, false, false, Double.NaN, Double.NaN)
            }
            val value = sample.toDouble()
            energy += value * value
            peak = maxOf(peak, abs(value))
            if (!energy.isFinite()) {
                return Result(pcm.size, true, false, false, Double.NaN, peak)
            }
        }
        val rms = sqrt(energy / pcm.size)
        val valid = rms.isFinite() && peak.isFinite()
        return Result(pcm.size, true, energy.isFinite(), valid, rms, peak)
    }
}
