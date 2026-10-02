package com.vico.simulator.sound

class GainEnvelope(private val smoothing: Float = 0.3f) {
    var value: Float = 0f
        private set

    fun step(audible: Boolean): Float {
        val target = if (audible) 1f else 0f
        value += (target - value) * smoothing
        if (!audible && value < 0.001f) value = 0f
        return value
    }
}
