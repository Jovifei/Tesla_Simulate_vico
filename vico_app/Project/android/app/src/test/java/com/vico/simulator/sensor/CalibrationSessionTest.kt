package com.vico.simulator.sensor

import org.junit.Assert.*
import org.junit.Test

class CalibrationSessionTest {
    private val sample = floatArrayOf(0.1f, 0.2f, 0.3f)
    private fun fill(session: CalibrationSession, count: Int = 24, from: Long = 100) {
        repeat(count) { session.add(sample, from + it) }
    }

    @Test fun zeroAndTwentyThreeSamplesCannotFinish() {
        for (count in listOf(0, 23)) {
            val s = CalibrationSession(); s.begin("a", 100); fill(s, count)
            assertFalse(s.finish("a")); assertFalse(s.isCalibrated)
            assertEquals(CalibrationSession.Status.FAILED, s.snapshot.status)
            fill(s); assertEquals(count, s.snapshot.samples)
        }
    }
    @Test fun twentyFourAcceptedSamplesCompleteOnlyOnMatchingFinish() {
        val s = CalibrationSession(); s.begin("a", 100); fill(s)
        assertFalse(s.isCalibrated); assertEquals(24, s.snapshot.samples)
        assertFalse(s.finish("stale")); assertTrue(s.finish("a")); assertTrue(s.isCalibrated)
        assertArrayEquals(FloatArray(3), s.correct(sample), 0.0001f)
        fill(s); assertEquals(24, s.snapshot.samples)
    }
    @Test fun newAttemptClearsOldSuccessAndBias() {
        val s = CalibrationSession(); s.begin("a", 100); fill(s); s.finish("a")
        s.begin("b", 200); assertFalse(s.isCalibrated); assertEquals(0, s.snapshot.samples)
        assertArrayEquals(sample, s.correct(sample), 0f)
        assertFalse(s.finish("a")); assertEquals(CalibrationSession.Status.SAMPLING, s.snapshot.status)
    }
    @Test fun duplicateBeginDoesNotEraseAcceptedSamples() {
        val s = CalibrationSession(); s.begin("a", 100); fill(s, 5)
        s.begin("a", 200); assertEquals(5, s.snapshot.samples)
    }
    @Test fun cancelResetAndStopEquivalentInvalidatePendingCompletion() {
        for (reset in listOf(false, true)) {
            val s = CalibrationSession(); s.begin("a", 100); fill(s)
            if (reset) s.reset() else s.cancel()
            assertFalse(s.finish("a")); assertFalse(s.isCalibrated)
            fill(s); assertEquals(0, s.snapshot.samples)
            assertArrayEquals(sample, s.correct(sample), 0f)
        }
    }
    @Test fun staleCancellationCannotCancelNewerSession() {
        val s = CalibrationSession(); s.begin("a", 100); s.begin("b", 200)
        s.cancel("a"); assertEquals(CalibrationSession.Status.SAMPLING, s.snapshot.status)
        fill(s, from = 200); assertTrue(s.finish("b"))
    }
    @Test fun invalidAndBeforeBeginSamplesDoNotCount() {
        val s = CalibrationSession(); s.begin("a", 100)
        s.add(sample, 99); s.add(floatArrayOf(1f), 100)
        s.add(floatArrayOf(Float.NaN, 0f, 0f), 101)
        s.add(floatArrayOf(0f, Float.POSITIVE_INFINITY, 0f), 102)
        assertEquals(0, s.snapshot.samples); fill(s); assertTrue(s.finish("a"))
    }
    @Test fun inactiveBeginFailsAndCannotBeCompleted() {
        val s = CalibrationSession(); s.begin("a", 100, available = false); fill(s)
        assertEquals(CalibrationSession.Status.FAILED, s.snapshot.status)
        assertFalse(s.finish("a")); assertEquals(0, s.snapshot.samples)
    }
    @Test fun revisionIncreasesAndCompletedCalibrationSurvivesOrdinaryStop() {
        val s = CalibrationSession(); val first = s.snapshot.revision
        s.begin("a", 100); fill(s); s.finish("a")
        assertTrue(s.snapshot.revision > first)
        val completed = s.snapshot; s.cancel(); assertEquals(completed, s.snapshot)
    }
    @Test fun onlyFreshOrderedAcceptedProviderSamplesCount() {
        val input = LinearAccelerationState()
        val session = CalibrationSession()
        val now = 1_000_000_000L
        session.begin("a", now)
        fun deliver(values: FloatArray, timestamp: Long, observed: Long) {
            if (input.update(values, timestamp, observed)) session.add(input.sample(), timestamp)
        }
        deliver(sample, now - 1, now) // Accepted by input, but before calibration began.
        repeat(24) { deliver(sample, now - 1, now) } // Duplicate timestamp.
        deliver(sample, now - 300_000_000L, now) // Stale and out of order.
        deliver(sample, now + 1, now) // Future timestamp.
        deliver(floatArrayOf(Float.NaN, 0f, 0f), now, now)
        assertEquals(0, session.snapshot.samples)
        repeat(23) { deliver(sample, now + it, now + it) }
        assertEquals(23, session.snapshot.samples)
        deliver(sample, now + 22, now + 23) // Duplicate must not become sample 24.
        assertEquals(23, session.snapshot.samples)
        deliver(sample, now + 23, now + 23)
        assertTrue(session.finish("a"))
    }

    @Test fun finiteSamplesWithOverflowedBiasFailClosedBeforePublication() {
        val s = CalibrationSession(); s.begin("a", 100)
        repeat(24) { s.add(floatArrayOf(Float.MAX_VALUE, Float.MAX_VALUE, Float.MAX_VALUE), 100L + it) }
        assertEquals(CalibrationSession.Status.FAILED, s.snapshot.status)
        assertFalse(s.finish("a")); assertFalse(s.isCalibrated)
        assertArrayEquals(sample, s.correct(sample), 0f)
    }

}
