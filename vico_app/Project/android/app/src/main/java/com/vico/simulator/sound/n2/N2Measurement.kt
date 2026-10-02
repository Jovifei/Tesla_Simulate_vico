package com.vico.simulator.sound.n2

object N2Measurement {
    fun rms(pcm: FloatArray): Double {
        if (pcm.isEmpty()) return 0.0
        var s = 0.0
        pcm.forEach { s += it * it }
        return kotlin.math.sqrt(s / pcm.size)
    }

    fun finite(pcm: FloatArray): Boolean = pcm.all { it.isFinite() }
}
