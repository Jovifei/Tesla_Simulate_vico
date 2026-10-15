package com.vico.simulator.sound

import kotlin.math.exp
import kotlin.math.max
import kotlin.math.sqrt

data class NormalEnvelopeSnapshot(val processedFrames: Long, val minGain: Double, val maxGain: Double)

/** Bounded normal drymix amplitude shaping; not a phase or source repair. */
internal class NormalEnvelopeDamper(private val sampleRateHz: Int) {
    private val fastAlpha = 1.0 - exp(-1.0 / (sampleRateHz * .050))
    private val slowAlpha = 1.0 - exp(-1.0 / (sampleRateHz * .600))
    private val gainAlpha = 1.0 - exp(-1.0 / (sampleRateHz * .005))
    private val warmupFrames = sampleRateHz / 4
    private var frames = 0L
    private var fastEnergy = 0.0
    private var slowEnergy = 0.0
    private var gain = 1.0
    private var minGain = 1.0
    private var maxGain = 1.0
    init { require(sampleRateHz > 0) }

    // Normal renderer owns this state. No allocations, files, blocks or future samples.
    fun process(sample: Float): Float {
        require(sample.isFinite())
        val energy = sample.toDouble() * sample
        fastEnergy += fastAlpha * (energy - fastEnergy)
        slowEnergy += slowAlpha * (energy - slowEnergy)
        frames++
        if (frames <= warmupFrames) return sample
        val target = if (max(fastEnergy, slowEnergy) < 1e-10) 1.0 else
            (1.0 + .3 * (sqrt((slowEnergy + 1e-12) / (fastEnergy + 1e-12)) - 1.0))
                .coerceIn(.97, 1.03)
        gain += gainAlpha * (target - gain)
        minGain = minOf(minGain, gain)
        maxGain = maxOf(maxGain, gain)
        return (sample * gain).toFloat()
    }

    fun reset() {
        frames = 0L
        fastEnergy = 0.0
        slowEnergy = 0.0
        gain = 1.0
        minGain = 1.0
        maxGain = 1.0
    }

    fun snapshot() = NormalEnvelopeSnapshot(frames, minGain, maxGain)
}
