package com.vico.simulator.sensor

/** Engineering safety thresholds, configurable for testing; not a road-accuracy claim. */
enum class GpsQuality { FRESH, UNVERIFIED, STALE, LOW_QUALITY, UNAVAILABLE, SYNTHETIC }
enum class ImuQuality { FRESH, UNCONFIRMED_FRAME, UNAVAILABLE, SYNTHETIC }

data class InputQualitySnapshot(
    val gps: GpsQuality,
    val imu: ImuQuality,
    val gpsAgeMs: Double?,
    val imuAgeMs: Double?,
    val validUntilElapsedNanos: Long,
) {
    val speedUsable: Boolean get() = gps in setOf(GpsQuality.FRESH, GpsQuality.UNVERIFIED, GpsQuality.SYNTHETIC)
    val accelerationUsable: Boolean get() = imu == ImuQuality.FRESH || imu == ImuQuality.SYNTHETIC
    val controlUsable: Boolean get() = speedUsable && accelerationUsable
    fun toJson(): String = "{\"gps\":\"${gps.name}\",\"imu\":\"${imu.name}\",\"speedUsable\":$speedUsable," +
        "\"accelerationUsable\":$accelerationUsable,\"controlUsable\":$controlUsable," +
        "\"gpsAgeMs\":${gpsAgeMs ?: "null"},\"imuAgeMs\":${imuAgeMs ?: "null"}}"
}

class InputQualityPolicy(
    private val freshGpsNanos: Long = 1_500_000_000L,
    private val freshImuNanos: Long = 250_000_000L,
    private val maximumSpeedUncertaintyMps: Double = 2.0,
) {
    init {
        require(freshGpsNanos > 0 && freshImuNanos > 0)
        require(maximumSpeedUncertaintyMps.isFinite() && maximumSpeedUncertaintyMps >= 0)
    }
    fun assess(input: InputDiagnostics, nowElapsedNanos: Long, frameConfirmed: Boolean): InputQualitySnapshot {
        if (input.sourceMode == InputDiagnostics.SourceMode.DEMO) return InputQualitySnapshot(
            GpsQuality.SYNTHETIC, ImuQuality.SYNTHETIC, null, null, Long.MAX_VALUE)
        val gpsAge = input.gpsTiming?.let { nowElapsedNanos - it.sourceElapsedNanos }
        val imuAge = input.imuTiming?.let { nowElapsedNanos - it.sourceElapsedNanos }
        val gps = when {
            !input.gpsValid || gpsAge == null || gpsAge < 0 -> GpsQuality.UNAVAILABLE
            gpsAge > freshGpsNanos -> GpsQuality.STALE
            input.gpsAccuracy?.status == SpeedAccuracy.Status.INVALID -> GpsQuality.LOW_QUALITY
            input.gpsAccuracy?.status == SpeedAccuracy.Status.AVAILABLE ->
                if ((input.gpsAccuracy.metersPerSecond ?: Double.POSITIVE_INFINITY) <= maximumSpeedUncertaintyMps)
                    GpsQuality.FRESH else GpsQuality.LOW_QUALITY
            else -> GpsQuality.UNVERIFIED
        }
        val imu = when {
            !input.imuValid || imuAge == null || imuAge !in 0..freshImuNanos -> ImuQuality.UNAVAILABLE
            !frameConfirmed -> ImuQuality.UNCONFIRMED_FRAME
            else -> ImuQuality.FRESH
        }
        val deadline = minOf(
            input.gpsTiming?.sourceElapsedNanos?.let { safeDeadline(it, freshGpsNanos) } ?: nowElapsedNanos,
            input.imuTiming?.sourceElapsedNanos?.let { safeDeadline(it, freshImuNanos) } ?: nowElapsedNanos)
        return InputQualitySnapshot(gps, imu, gpsAge?.takeIf { it >= 0 }?.div(1e6),
            imuAge?.takeIf { it >= 0 }?.div(1e6), deadline)
    }
    private fun safeDeadline(source: Long, freshness: Long) =
        if (source > Long.MAX_VALUE - freshness) Long.MAX_VALUE else source + freshness
}

/** Keeps discontinuities observable even when the audio consumer skips intermediate frames. */
class InputContinuityTracker {
    private var epoch = 0L
    private var source: String? = null
    private var wasUsable = false
    private var deadline = 0L
    fun advance(sourceKey: String, usable: Boolean, validUntilNanos: Long, nowNanos: Long): Long {
        if (sourceKey != source || usable != wasUsable || wasUsable && nowNanos > deadline) epoch++
        source = sourceKey
        wasUsable = usable
        deadline = validUntilNanos
        return epoch
    }
}
