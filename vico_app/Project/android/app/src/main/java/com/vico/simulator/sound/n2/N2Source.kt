package com.vico.simulator.sound.n2

import kotlin.math.PI
import kotlin.math.sin

class N2Source(private val profile: N2Profile = N2Profile()) {
    fun continuous(samples: Int, state: Double): FloatArray {
        require(samples >= 0)
        val out = FloatArray(samples)
        for (i in out.indices) {
            val t = i.toDouble() / profile.sampleRate
            var value = 0.0
            for (k in 1..profile.basisCount) {
                value += (0.05 / k) * sin(2.0 * PI * (80.0 * k) * t + state)
            }
            out[i] = value.toFloat()
        }
        return out
    }

    fun event(seed: Long = profile.seed): FloatArray {
        val out = FloatArray(profile.eventLength)
        var x = seed
        for (i in out.indices) {
            x = x * 6364136223846793005L + 1442695040888963407L
            out[i] = (((x ushr 40) and 0xffff) / 65535.0f - 0.5f) * 0.04f
        }
        return out
    }
}
