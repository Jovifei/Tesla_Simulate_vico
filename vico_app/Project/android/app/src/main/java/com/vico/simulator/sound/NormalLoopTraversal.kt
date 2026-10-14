package com.vico.simulator.sound

import java.util.IdentityHashMap
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.floor

enum class LoopTraversalMode { LEGACY_LOCKED, NORMAL_CANONICAL_SEAM_V1 }

data class LoopTraversalSnapshot(
    val correctedReads: Long = 0, val skippedShortLoopReads: Long = 0, val maxAbsCorrection: Double = 0.0,
)

/** Pure canonical reading plus compact slope corrections at the two wrapping junctions. */
internal class NormalLoopTraversal(bank: MatlabSoundBank, @Suppress("UNUSED_PARAMETER") identity: String) {
    private class Prepared(loop: MatlabLoop, sampleRate: Int) {
        val spanCycles = loop.samples.size.toDouble() / sampleRate * loop.rpm / 120.0
        val eligible = loop.samples.size >= 3 && SUPPORT_SAMPLES <= .20 * loop.samples.size
        val delta1: Double
        val delta2: Double
        init {
            val x = loop.samples
            if (eligible) {
                val wrap = x[0].toDouble() - x.last()
                delta1 = wrap - (x.last().toDouble() - x[x.lastIndex - 1])
                delta2 = (x[1].toDouble() - x[0]) - wrap
            } else { delta1 = 0.0; delta2 = 0.0 }
        }
    }
    private val prepared = IdentityHashMap<MatlabLoop, Prepared>().apply {
        for (loop in bank.loops) put(loop, Prepared(loop, bank.sampleRateHz))
    }
    private var correctedReads = 0L
    private var skippedShortReads = 0L
    private var correctionPeak = 0.0

    fun reset() { correctedReads = 0L; skippedShortReads = 0L; correctionPeak = 0.0 }

    fun sample(loop: MatlabLoop, engineCycles: Double): Float {
        val info = prepared.getValue(loop)
        val samples = loop.samples
        if (samples.isEmpty() || info.spanCycles <= 0.0) return 0f
        val position = (engineCycles % info.spanCycles) / info.spanCycles * samples.size
        val first = floor(position).toInt() % samples.size
        val second = (first + 1) % samples.size
        val legacy = samples[first] + (samples[second] - samples[first]) * (position - floor(position)).toFloat()
        if (!info.eligible) { skippedShortReads++; return legacy }
        if (position >= HALF_WIDTH && position <= samples.lastIndex - HALF_WIDTH) return legacy
        val atZero = if (position > samples.size / 2.0) position - samples.size else position
        var atLast = position - samples.lastIndex
        if (atLast < -samples.size / 2.0) atLast += samples.size
        val correction = soften(atLast, info.delta1) + soften(atZero, info.delta2)
        if (correction == 0.0) return legacy
        correctedReads++
        correctionPeak = maxOf(correctionPeak, abs(correction))
        return (legacy.toDouble() + correction).toFloat()
    }

    private fun soften(distance: Double, delta: Double): Double {
        val u = abs(distance)
        if (u >= HALF_WIDTH) return 0.0
        return -delta / 2.0 * u * (1.0 + cos(PI * u / HALF_WIDTH)) / 2.0
    }

    fun stats() = LoopTraversalSnapshot(correctedReads = correctedReads, skippedShortLoopReads = skippedShortReads, maxAbsCorrection = correctionPeak)

    companion object {
        private const val HALF_WIDTH = 8.0
        private const val SUPPORT_SAMPLES = 17.0
    }
}
