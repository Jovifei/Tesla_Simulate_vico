package com.vico.simulator.sensor

class LocationSpeedState(private val freshnessNanos: Long = 3_000_000_000L) {
    @Volatile var speedKmh: Double = 0.0
        private set
    @Volatile var gpsOk: Boolean = false
        private set

    private var lastFixElapsedNanos: Long = 0L

    fun update(
        speedMps: Double,
        hasSpeed: Boolean,
        fixElapsedNanos: Long,
        nowElapsedNanos: Long,
    ): Boolean {
        val age = nowElapsedNanos - fixElapsedNanos
        if (!hasSpeed || speedMps < 0.0 || fixElapsedNanos <= 0L || age !in 0..freshnessNanos) {
            return false
        }
        speedKmh = speedMps * 3.6
        gpsOk = true
        lastFixElapsedNanos = fixElapsedNanos
        return true
    }

    fun expire(nowElapsedNanos: Long) {
        if (lastFixElapsedNanos == 0L || nowElapsedNanos - lastFixElapsedNanos > freshnessNanos) {
            clear()
        }
    }

    fun clear() {
        speedKmh = 0.0
        gpsOk = false
        lastFixElapsedNanos = 0L
    }
}
