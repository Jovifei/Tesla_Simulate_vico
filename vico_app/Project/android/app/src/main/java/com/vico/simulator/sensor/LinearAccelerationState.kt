package com.vico.simulator.sensor

/** Latest measured device-axis acceleration, never a predicted vehicle acceleration. */
class LinearAccelerationState(private val freshnessNanos: Long = 250_000_000L) {
    private var values = FloatArray(3)
    private var lastSampleElapsedNanos = 0L
    var valid: Boolean = false
        private set

    fun update(sample: FloatArray, sampleElapsedNanos: Long, nowElapsedNanos: Long): Boolean {
        if (sample.size < 3 || (0..2).any { !sample[it].isFinite() } ||
            sampleElapsedNanos <= lastSampleElapsedNanos ||
            nowElapsedNanos - sampleElapsedNanos !in 0..freshnessNanos) return false
        values = sample.copyOf(3)
        lastSampleElapsedNanos = sampleElapsedNanos
        valid = true
        return true
    }

    fun sample(): FloatArray = values.copyOf()

    fun expire(nowElapsedNanos: Long) {
        if (lastSampleElapsedNanos == 0L || nowElapsedNanos - lastSampleElapsedNanos !in 0..freshnessNanos) clear()
    }

    fun clear() {
        values = FloatArray(3)
        lastSampleElapsedNanos = 0L
        valid = false
    }
}
