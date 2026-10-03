package com.vico.simulator.sensor

data class LocationSpeedSample(
    val speedMps: Double,
    val hasSpeed: Boolean,
    val elapsedNanos: Long,
    val speedAccuracy: SpeedAccuracy = SpeedAccuracy.fromPlatform(true, false, null),
)

class LocationSpeedState(private val freshnessNanos: Long = 3_000_000_000L) {
    @Volatile var speedKmh: Double = 0.0
        private set
    @Volatile var gpsOk: Boolean = false
        private set

    private var lastFixElapsedNanos: Long = 0L
    var lastAcceptedTiming: SampleTiming? = null
        private set
    var speedAccuracy: SpeedAccuracy? = null
        private set

    fun update(
        speedMps: Double,
        hasSpeed: Boolean,
        fixElapsedNanos: Long,
        nowElapsedNanos: Long,
        accuracy: SpeedAccuracy = SpeedAccuracy.fromPlatform(true, false, null),
        receivedElapsedNanos: Long = nowElapsedNanos,
    ): Boolean {
        val age = nowElapsedNanos - fixElapsedNanos
        if (!hasSpeed || !speedMps.isFinite() || speedMps < 0.0 || !(speedMps * 3.6).isFinite() ||
            fixElapsedNanos <= lastFixElapsedNanos || age !in 0..freshnessNanos) {
            return false
        }
        speedKmh = speedMps * 3.6
        gpsOk = true
        lastFixElapsedNanos = fixElapsedNanos
        lastAcceptedTiming = SampleTiming(fixElapsedNanos, receivedElapsedNanos)
        speedAccuracy = accuracy
        return true
    }

    /** A newer invalid fix must not hide an older usable measurement in the same batch. */
    fun updateLatest(samples: List<LocationSpeedSample>, nowElapsedNanos: Long, receivedElapsedNanos: Long = nowElapsedNanos): Boolean =
        samples.sortedByDescending { it.elapsedNanos }.any {
            update(it.speedMps, it.hasSpeed, it.elapsedNanos, nowElapsedNanos, it.speedAccuracy, receivedElapsedNanos)
        }

    fun expire(nowElapsedNanos: Long) {
        if (lastFixElapsedNanos == 0L || nowElapsedNanos - lastFixElapsedNanos !in 0..freshnessNanos) {
            clearValues()
        }
    }

    fun clear() {
        clearValues()
        lastAcceptedTiming = null
        speedAccuracy = null
    }

    private fun clearValues() {
        speedKmh = 0.0
        gpsOk = false
        lastFixElapsedNanos = 0L
    }
}
