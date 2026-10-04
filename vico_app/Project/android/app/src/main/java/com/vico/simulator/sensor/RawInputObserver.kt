package com.vico.simulator.sensor

/** Optional diagnostic tap on real callbacks only; never a location/coordinate stream. */
interface RawInputObserver {
    fun gps(sourceNanos: Long, receivedNanos: Long, speedMps: Double?, accuracy: SpeedAccuracy, accepted: Boolean, hasSpeed: Boolean)
    fun imu(sourceNanos: Long, receivedNanos: Long, values: FloatArray, bias: FloatArray, accepted: Boolean)
}
