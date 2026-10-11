package com.vico.simulator.sensor

import org.junit.Assert.*
import org.junit.Test
import java.util.Locale

class InputDiagnosticsTest {
    private val sample = floatArrayOf(0f, 1f, 2f)
    private fun ms(value: Long) = value * 1_000_000L

    @Test fun repeatedTicksRetainIdentityWhileSameValueNewFixesAdvanceIt() {
        val gps = LocationSpeedState()
        assertTrue(gps.update(10.0, true, ms(1000), ms(1180)))
        val first = gps.lastAcceptedTiming
        val ages = (0..19).map { tick ->
            val published = ms(1220 + tick * 50L)
            InputDiagnostics(publishElapsedNanos = published, gpsTiming = gps.lastAcceptedTiming).gpsAgeMs
        }
        assertEquals(first, gps.lastAcceptedTiming)
        assertEquals(220.0, ages.first()!!, 0.0); assertEquals(1170.0, ages.last()!!, 0.0)
        val identities = (0..19).map { n ->
            val source = ms(2000 + n * 100L)
            assertTrue(gps.update(10.0, true, source, source + ms(10)))
            gps.lastAcceptedTiming!!.sourceElapsedNanos
        }
        assertEquals(20, identities.toSet().size)
    }
    @Test fun timestampsReconstructDelayedCallbackAndPublicationWithoutWallClock() {
        val timing = SampleTiming(ms(1000), ms(1180))
        val d = InputDiagnostics(inputSession = 1, publishElapsedNanos = ms(1220),
            consumeElapsedNanos = ms(1223), gpsTiming = timing, gpsValid = true)
        assertEquals(220.0, d.gpsAgeMs!!, 0.0)
        assertEquals(ms(180), timing.receivedElapsedNanos - timing.sourceElapsedNanos)
        val published = requireNotNull(d.publishElapsedNanos)
        val consumed = requireNotNull(d.consumeElapsedNanos)
        assertEquals(ms(40), published - timing.receivedElapsedNanos)
        assertEquals(ms(3), consumed - published)
    }
    @Test fun gpsExpiryPreservesObservationalIdentityButExplicitClearDoesNot() {
        val gps = LocationSpeedState(); gps.update(5.0, true, ms(1000), ms(1000))
        val identity = gps.lastAcceptedTiming
        gps.expire(ms(4000)); assertTrue(gps.gpsOk)
        gps.expire(ms(4000) + 1); assertFalse(gps.gpsOk); assertEquals(0.0, gps.speedKmh, 0.0)
        assertEquals(identity, gps.lastAcceptedTiming)
        gps.clear(); assertNull(gps.lastAcceptedTiming); assertNull(gps.speedAccuracy)
    }
    @Test fun imuExpiryPreservesIdentityAndNewSampleRecovers() {
        val imu = LinearAccelerationState(); imu.update(sample, ms(1000), ms(1000))
        val identity = imu.lastAcceptedTiming
        imu.expire(ms(1250)); assertTrue(imu.valid)
        imu.expire(ms(1250) + 1); assertFalse(imu.valid); assertArrayEquals(FloatArray(3), imu.sample(), 0f)
        assertEquals(identity, imu.lastAcceptedTiming)
        assertTrue(imu.update(sample, ms(1251), ms(1252))); assertTrue(imu.valid)
        assertEquals(ms(1252), imu.lastAcceptedTiming!!.receivedElapsedNanos)
        imu.clear(); assertNull(imu.lastAcceptedTiming)
    }
    @Test fun rejectedSamplesCannotReplaceMetadata() {
        val gps = LocationSpeedState(); gps.update(5.0, true, ms(1000), ms(1010))
        val first = gps.lastAcceptedTiming
        for (timestamp in listOf(ms(1000), ms(999), ms(2000), ms(1))) {
            assertFalse(gps.update(8.0, true, timestamp, ms(1100)))
            assertEquals(first, gps.lastAcceptedTiming)
        }
        for (speed in listOf(Double.NaN, Double.POSITIVE_INFINITY, -1.0)) {
            assertFalse(gps.update(speed, true, ms(1100), ms(1100)))
            assertEquals(first, gps.lastAcceptedTiming)
        }
        assertFalse(gps.update(10.0, false, ms(1100), ms(1100)))
        val imu = LinearAccelerationState(); imu.update(sample, ms(1000), ms(1010))
        val imuFirst = imu.lastAcceptedTiming
        assertFalse(imu.update(floatArrayOf(Float.NaN, 1f, 2f), ms(1100), ms(1100)))
        assertFalse(imu.update(sample, ms(999), ms(1100)))
        assertEquals(imuFirst, imu.lastAcceptedTiming)
    }
    @Test fun delayedBatchKeepsAccuracyAndTimingOfTheSameAcceptedFix() {
        val gps = LocationSpeedState()
        val good = SpeedAccuracy.fromPlatform(true, true, 0.5)
        val other = SpeedAccuracy.fromPlatform(true, true, 99.0)
        val accepted = LocationSpeedSample(4.0, true, ms(1000), good)
        val invalid = LocationSpeedSample(Double.NaN, true, ms(1100), other)
        assertTrue(gps.updateLatest(listOf(accepted, invalid), ms(1300)))
        assertEquals(14.4, gps.speedKmh, 0.0001)
        assertEquals(SampleTiming(ms(1000), ms(1300)), gps.lastAcceptedTiming)
        assertEquals(good, gps.speedAccuracy)
        assertTrue(gps.updateLatest(listOf(LocationSpeedSample(7.0, true, ms(1400), other), accepted), ms(1600)))
        assertEquals(SampleTiming(ms(1400), ms(1600)), gps.lastAcceptedTiming)
        assertEquals(other, gps.speedAccuracy)
    }
    @Test fun speedAccuracyDistinguishesUnsupportedAbsentInvalidAndRealZero() {
        assertEquals(SpeedAccuracy.Status.UNSUPPORTED_API, SpeedAccuracy.fromPlatform(false, false, null).status)
        assertEquals(SpeedAccuracy.Status.NOT_REPORTED, SpeedAccuracy.fromPlatform(true, false, 0.0).status)
        for (value in listOf(-1.0, Double.NaN, Double.POSITIVE_INFINITY)) {
            val result = SpeedAccuracy.fromPlatform(true, true, value)
            assertEquals(SpeedAccuracy.Status.INVALID, result.status); assertNull(result.metersPerSecond)
        }
        val zero = SpeedAccuracy.fromPlatform(true, true, 0.0)
        assertEquals(SpeedAccuracy.Status.AVAILABLE, zero.status); assertEquals(0.0, zero.metersPerSecond!!, 0.0)
    }
    @Test fun unavailableAccuracyDoesNotChangeSpeedAcceptance() {
        val gps = LocationSpeedState()
        listOf(SpeedAccuracy.fromPlatform(false, false, null), SpeedAccuracy.fromPlatform(true, false, null),
            SpeedAccuracy.fromPlatform(true, true, Double.NaN), SpeedAccuracy.fromPlatform(true, true, 0.0)).forEachIndexed { i, a ->
            assertTrue(gps.updateLatest(listOf(LocationSpeedSample(2.0, true, ms(1000 + i.toLong()), a)), ms(1100)))
            assertEquals(7.2, gps.speedKmh, 0.0001)
        }
    }
    @Test fun demoUsesSyntheticValuesButKeepsExplicitPhysicalInputProvenance() {
        val realDiagnostics = InputDiagnostics(inputSession = 3, publishElapsedNanos = ms(1000),
            gpsTiming = SampleTiming(ms(990), ms(995)), gpsValid = false)
        val state = SensorSourceState()
        state.updateReal(SensorFrame(0.0, 0.0, false, FloatArray(3), realDiagnostics))
        state.updateDemo(SensorFrame(80.0, 2.0, true, sample))
        val demo = state.setDemoMode(true)
        assertTrue(demo.gpsOk); assertFalse(demo.diagnostics.gpsValid)
        assertEquals(InputDiagnostics.SourceMode.DEMO, demo.diagnostics.sourceMode)
        assertEquals(realDiagnostics.gpsTiming, demo.diagnostics.gpsTiming)
        assertEquals(InputDiagnostics.SourceMode.REAL, state.setDemoMode(false).diagnostics.sourceMode)
    }
    @Test fun previewAndReferenceModesDoNotAlterPhysicalSampleIdentity() {
        val d = InputDiagnostics(gpsTiming = SampleTiming(1, 2))
        for (mode in InputDiagnostics.DriveInputMode.values()) {
            val consumed = d.copy(consumeElapsedNanos = 5, driveInputMode = mode)
            assertEquals(d.gpsTiming, consumed.gpsTiming)
            assertTrue(consumed.toJson().contains("\"drive_input_mode\":\"${mode.name}\""))
        }
    }
    @Test fun jsonNanosecondsAboveSafeIntegerRemainExactStrings() {
        val large = 9_007_199_254_740_999L
        val d = InputDiagnostics(publishElapsedNanos = large + 2, consumeElapsedNanos = large + 3,
            gpsTiming = SampleTiming(large, large + 1), imuTiming = SampleTiming(large, large + 1))
        val json = d.toJson()
        assertTrue(json.contains("\"gps_sample_elapsed_ns\":\"$large\""))
        assertTrue(json.contains("\"publish_elapsed_ns\":\"${large + 2}\""))
        assertEquals(0.000002, d.gpsAgeMs!!, 0.0)
        assertTrue(d.toCsvColumns().split(',').contains(large.toString()))
    }
    @Test fun nullAndZeroStayDistinctAndCsvIsLocaleIndependent() {
        val old = Locale.getDefault()
        try {
            Locale.setDefault(Locale.GERMANY)
            val empty = InputDiagnostics()
            assertTrue(empty.toJson().contains("\"gps_sample_elapsed_ns\":null"))
            assertTrue(empty.toJson().contains("\"gps_speed_accuracy_mps\":null"))
            assertEquals(16, empty.toCsvColumns().split(',').size)
            val zero = InputDiagnostics(publishElapsedNanos = 10, gpsTiming = SampleTiming(10, 10),
                gpsAccuracy = SpeedAccuracy.fromPlatform(true, true, 0.0))
            assertEquals(0.0, zero.gpsAgeMs!!, 0.0)
            assertTrue(zero.toJson().contains("\"gps_speed_accuracy_mps\":0.0"))
            assertEquals(16, zero.toCsvColumns().split(',').size)
            assertEquals(16, InputDiagnostics.CSV_HEADER.split(',').size)
        } finally { Locale.setDefault(old) }
    }
    @Test fun invalidClockComparisonDoesNotInventZeroAge() {
        val d = InputDiagnostics(publishElapsedNanos = 9, gpsTiming = SampleTiming(10, 10))
        assertNull(d.gpsAgeMs); assertFalse(d.toJson().contains("NaN"))
    }
    @Test fun completeEmptyJsonAndHeaderHaveStableSixteenFieldSchema() {
        assertEquals("diagnostics_version,input_session,source_mode,drive_input_mode,publish_elapsed_ns,consume_elapsed_ns,gps_sample_elapsed_ns,gps_received_elapsed_ns,gps_age_ms,gps_valid,gps_speed_accuracy_status,gps_speed_accuracy_mps,imu_sample_elapsed_ns,imu_received_elapsed_ns,imu_age_ms,imu_valid", InputDiagnostics.CSV_HEADER)
        assertEquals("{\"diagnostics_version\":1,\"input_session\":0,\"source_mode\":\"REAL\",\"drive_input_mode\":\"LIVE\",\"publish_elapsed_ns\":null,\"consume_elapsed_ns\":null,\"gps_sample_elapsed_ns\":null,\"gps_received_elapsed_ns\":null,\"gps_age_ms\":null,\"gps_valid\":false,\"gps_speed_accuracy_status\":null,\"gps_speed_accuracy_mps\":null,\"imu_sample_elapsed_ns\":null,\"imu_received_elapsed_ns\":null,\"imu_age_ms\":null,\"imu_valid\":false}", InputDiagnostics().toJson())
    }

    @Test fun receiptTimestampDoesNotReplaceFreshnessValidationClock() {
        val gps = LocationSpeedState()
        assertFalse(gps.updateLatest(listOf(LocationSpeedSample(2.0, true, ms(1000))), ms(4001), ms(1100)))
        assertNull(gps.lastAcceptedTiming)
        assertTrue(gps.updateLatest(listOf(LocationSpeedSample(2.0, true, ms(1000))), ms(2000), ms(1100)))
        assertEquals(SampleTiming(ms(1000), ms(1100)), gps.lastAcceptedTiming)
        val imu = LinearAccelerationState()
        assertFalse(imu.update(sample, ms(1000), ms(1251), ms(1100)))
        assertNull(imu.lastAcceptedTiming)
        assertTrue(imu.update(sample, ms(1000), ms(1250), ms(1100)))
        assertEquals(SampleTiming(ms(1000), ms(1100)), imu.lastAcceptedTiming)
    }

    @Test fun inputSnapshotCopiesPrimitiveValuesAndCannotAliasSensorArrays() {
        val raw = floatArrayOf(1f, 2f, 3f); val gravity = floatArrayOf(4f, 5f, 6f)
        val d = InputDiagnostics(gpsTiming = SampleTiming(1, 2))
        val snapshot = SensorInputSnapshot.capture(7.0, 8.0, true, raw, gravity, d)
        raw.fill(99f); gravity.fill(99f)
        assertEquals(1f, snapshot.ax, 0f); assertEquals(5f, snapshot.gy, 0f)
        assertEquals(d, snapshot.diagnostics)
    }
    @Test fun immutableInputPublicationKeepsValuesAndDiagnosticIdentityTogether() {
        class Holder { @Volatile var snapshot = SensorInputSnapshot() }
        val holder = Holder()
        val writer = Thread {
            repeat(20000) { n -> holder.snapshot = SensorInputSnapshot(speedKmh = n.toDouble(),
                accelMps2 = n.toDouble(), diagnostics = InputDiagnostics(inputSession = n.toLong())) }
        }
        writer.start()
        repeat(20000) {
            val snapshot = holder.snapshot
            assertEquals(snapshot.speedKmh, snapshot.accelMps2, 0.0)
            assertEquals(snapshot.speedKmh.toLong(), snapshot.diagnostics.inputSession)
        }
        writer.join()
    }

}
