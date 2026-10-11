package com.vico.simulator.csv

import com.vico.simulator.sensor.InputDiagnostics
import java.util.Locale

/** Append-only App trace format; the first six fields retain their original contract. */
object CsvTraceFormat {
    const val HEADER = "time_s,speed_kmh,accel_mps2,rpm,freq_hz,profile," + InputDiagnostics.CSV_HEADER

    fun row(timeS: Double, speedKmh: Double, accelMps2: Double, rpm: Double, freqHz: Double,
            profileLabel: String, diagnostics: InputDiagnostics): String =
        String.format(Locale.US, "%.3f,%.1f,%.2f,%.0f,%.1f,%s",
            timeS, speedKmh, accelMps2, rpm, freqHz, profileLabel) + "," + diagnostics.toCsvColumns()
}
