package com.vico.simulator.sensor

class CalibrationAccumulator(private val requiredSamples: Int = 24) {

    private val sums = FloatArray(3)
    private var count = 0
    private val bias = FloatArray(3)

    val isReady: Boolean get() = count >= requiredSamples

    fun add(sample: FloatArray) {
        if (sample.size < 3 || isReady) return
        for (axis in 0..2) sums[axis] += sample[axis]
        count += 1
        if (isReady) {
            for (axis in 0..2) bias[axis] = sums[axis] / count
        }
    }

    fun offsets(): FloatArray = bias.copyOf()

    fun correct(sample: FloatArray): FloatArray = FloatArray(3) { axis ->
        (sample.getOrElse(axis) { 0f } - bias[axis])
    }

    fun reset() {
        sums.fill(0f)
        bias.fill(0f)
        count = 0
    }
}
