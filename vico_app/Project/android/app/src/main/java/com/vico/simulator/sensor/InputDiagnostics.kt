package com.vico.simulator.sensor

/** Monotonic input-pipeline times only; these do not measure physical or speaker latency. */
data class SampleTiming(val sourceElapsedNanos: Long, val receivedElapsedNanos: Long) {
    fun ageMs(publishedElapsedNanos: Long?): Double? =
        if (publishedElapsedNanos != null && publishedElapsedNanos >= sourceElapsedNanos)
            (publishedElapsedNanos - sourceElapsedNanos) / 1_000_000.0 else null
}

/** Provider-reported speed uncertainty, not a measured ground-truth error. */
data class SpeedAccuracy private constructor(val status: Status, val metersPerSecond: Double?) {
    enum class Status { AVAILABLE, NOT_REPORTED, UNSUPPORTED_API, INVALID }
    companion object {
        fun fromPlatform(apiSupported: Boolean, reported: Boolean, value: Double?): SpeedAccuracy = when {
            !apiSupported -> SpeedAccuracy(Status.UNSUPPORTED_API, null)
            !reported -> SpeedAccuracy(Status.NOT_REPORTED, null)
            value == null || !value.isFinite() || value < 0.0 -> SpeedAccuracy(Status.INVALID, null)
            else -> SpeedAccuracy(Status.AVAILABLE, value)
        }
    }
}

/** Immutable, coordinate-free snapshot. Persistence is only through existing user-started CSV recording. */
data class InputDiagnostics(
    val inputSession: Long = 0,
    val sourceMode: SourceMode = SourceMode.REAL,
    val driveInputMode: DriveInputMode = DriveInputMode.LIVE,
    val publishElapsedNanos: Long? = null,
    val consumeElapsedNanos: Long? = null,
    val gpsTiming: SampleTiming? = null,
    val gpsValid: Boolean = false,
    val gpsAccuracy: SpeedAccuracy? = null,
    val imuTiming: SampleTiming? = null,
    val imuValid: Boolean = false,
) {
    enum class SourceMode { REAL, DEMO }
    enum class DriveInputMode { LIVE, PREVIEW, REFERENCE_BYPASS }
    val gpsAgeMs: Double? get() = gpsTiming?.ageMs(publishElapsedNanos)
    val imuAgeMs: Double? get() = imuTiming?.ageMs(publishElapsedNanos)

    private fun fields(): List<String?> = listOf(
        "1", inputSession.toString(), sourceMode.name, driveInputMode.name,
        publishElapsedNanos?.toString(), consumeElapsedNanos?.toString(),
        gpsTiming?.sourceElapsedNanos?.toString(), gpsTiming?.receivedElapsedNanos?.toString(),
        gpsAgeMs?.toString(), gpsValid.toString(),
        gpsAccuracy?.takeIf { gpsTiming != null }?.status?.name,
        gpsAccuracy?.takeIf { gpsTiming != null }?.metersPerSecond?.toString(),
        imuTiming?.sourceElapsedNanos?.toString(), imuTiming?.receivedElapsedNanos?.toString(),
        imuAgeMs?.toString(), imuValid.toString(),
    )

    // Values are numbers, booleans, or controlled enum tokens: no free text needs CSV/JSON escaping.
    fun toCsvColumns(): String = fields().joinToString(",") { it ?: "" }

    fun toJson(): String = names.zip(fields()).joinToString(",", "{", "}") { (name, value) ->
        val encoded = if (value == null) "null" else if (name in stringFields) "\"$value\"" else value
        "\"$name\":$encoded"
    }

    companion object {
        const val CSV_HEADER = "diagnostics_version,input_session,source_mode,drive_input_mode,publish_elapsed_ns,consume_elapsed_ns,gps_sample_elapsed_ns,gps_received_elapsed_ns,gps_age_ms,gps_valid,gps_speed_accuracy_status,gps_speed_accuracy_mps,imu_sample_elapsed_ns,imu_received_elapsed_ns,imu_age_ms,imu_valid"
        private val names = CSV_HEADER.split(',')
        // Android nanosecond timestamps can exceed JavaScript's exact integer range. Keep exact decimal strings.
        private val stringFields = names.filter { it.endsWith("_elapsed_ns") }.toSet() +
            setOf("source_mode", "drive_input_mode", "gps_speed_accuracy_status")
    }
}
