package com.vico.simulator.sound.n2

class N2Renderer(private val source: N2Source = N2Source()) {
    fun render(mode: Mode, frames: Int, eventOn: Boolean): FloatArray {
        val continuous = source.continuous(frames, 0.0)
        if (!eventOn || (mode != Mode.E && mode != Mode.SE)) return continuous
        val event = source.event()
        for (i in continuous.indices) continuous[i] += event[i % event.size]
        return continuous
    }

    enum class Mode { T, S, E, SE }
}
