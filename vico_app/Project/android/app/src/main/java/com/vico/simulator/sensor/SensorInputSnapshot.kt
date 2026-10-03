package com.vico.simulator.sensor

/** One bridge-reader publication: source values and their provenance can never be read from different frames. */
data class SensorInputSnapshot(
    val speedKmh: Double = 0.0,
    val accelMps2: Double = 0.0,
    val gpsOk: Boolean = false,
    val ax: Float = 0f, val ay: Float = 0f, val az: Float = 0f,
    val gx: Float = 0f, val gy: Float = 0f, val gz: Float = 0f,
    val diagnostics: InputDiagnostics = InputDiagnostics(),
) {
    companion object {
        fun capture(speedKmh: Double, accelMps2: Double, gpsOk: Boolean,
                    raw: FloatArray, gravity: FloatArray, diagnostics: InputDiagnostics) = SensorInputSnapshot(
            speedKmh, accelMps2, gpsOk,
            raw.getOrElse(0) { 0f }, raw.getOrElse(1) { 0f }, raw.getOrElse(2) { 0f },
            gravity.getOrElse(0) { 0f }, gravity.getOrElse(1) { 0f }, gravity.getOrElse(2) { 0f },
            diagnostics,
        )
    }
}
