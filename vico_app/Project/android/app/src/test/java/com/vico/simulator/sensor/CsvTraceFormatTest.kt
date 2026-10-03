package com.vico.simulator.sensor

import com.vico.simulator.csv.CsvTraceFormat
import org.junit.Assert.*
import org.junit.Test
import java.util.Locale

class CsvTraceFormatTest {
    @Test fun oldSixFieldsRemainByteForByteAndExactlySixteenAreAppended() {
        val old = String.format(Locale.US, "%.3f,%.1f,%.2f,%.0f,%.1f,%s", 1.23456, 42.68, -1.234, 2300.4, 100.12, "车型/柔和")
        val row = CsvTraceFormat.row(1.23456, 42.68, -1.234, 2300.4, 100.12, "车型/柔和", InputDiagnostics())
        assertEquals(old, row.split(',').take(6).joinToString(","))
        assertEquals(22, row.split(',').size)
        assertTrue(row.startsWith(old + ","))
    }
    @Test fun headerPreservesNamesAndHasTwentyTwoUniqueFields() {
        val columns = CsvTraceFormat.HEADER.split(',')
        assertEquals("time_s,speed_kmh,accel_mps2,rpm,freq_hz,profile", columns.take(6).joinToString(","))
        assertEquals(22, columns.size); assertEquals(22, columns.toSet().size)
        assertEquals(InputDiagnostics.CSV_HEADER, columns.drop(6).joinToString(","))
    }
    @Test fun diagnosticTokensDoNotIntroduceCsvSeparatorsAndMissingAccuracyIsEmpty() {
        val d = InputDiagnostics(inputSession = 8, sourceMode = InputDiagnostics.SourceMode.DEMO,
            gpsTiming = SampleTiming(9007199254740999, 9007199254741999),
            gpsAccuracy = SpeedAccuracy.fromPlatform(false, false, null))
        val row = CsvTraceFormat.row(0.0, 0.0, 0.0, 0.0, 0.0, "vico", d)
        assertEquals(22, row.split(',').size); assertFalse(row.contains('\n'))
        assertEquals("UNSUPPORTED_API", row.split(',')[16]); assertEquals("", row.split(',')[17])
    }
}
