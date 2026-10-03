package com.vico.simulator.sensor

data class LocationSpeedSample(val speedMps: Double, val hasSpeed: Boolean, val elapsedNanos: Long)

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
        if (!hasSpeed || !speedMps.isFinite() || speedMps < 0.0 || !(speedMps * 3.6).isFinite() ||
            fixElapsedNanos <= lastFixElapsedNanos || age !in 0..freshnessNanos) {
            return false
        }
        speedKmh = speedMps * 3.6
        gpsOk = true
        lastFixElapsedNanos = fixElapsedNanos
        return true
    }

    /** A newer invalid fix must not hide an older usable measurement in the same batch. */
    fun updateLatest(samples: List<LocationSpeedSample>, nowElapsedNanos: Long): Boolean =
        samples.sortedByDescending { it.elapsedNanos }.any {
            update(it.speedMps, it.hasSpeed, it.elapsedNanos, nowElapsedNanos)
        }

    fun expire(nowElapsedNanos: Long) {
        if (lastFixElapsedNanos == 0L || nowElapsedNanos - lastFixElapsedNanos !in 0..freshnessNanos) {
            clear()
        }
    }

    fun clear() {
        speedKmh = 0.0
        gpsOk = false
        lastFixElapsedNanos = 0L
    }
}
