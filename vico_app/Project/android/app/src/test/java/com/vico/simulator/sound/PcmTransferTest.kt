package com.vico.simulator.sound

import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.*
import org.junit.Test

class PcmTransferTest {
    private fun rejectsWrite(block: () -> Unit) {
        try {
            block()
        } catch (_: IllegalStateException) {
            return
        }
        fail("Expected write failure")
    }

    @Test
    fun partial_writes_preserve_order_and_capture_only_accepted_samples() {
        val input = FloatArray(11) { it / 16f }
        val accepted = ArrayList<Float>()
        val capture = BoundedPcmCapture(11)
        writeAllPcm(input, capture) { data, offset, count ->
            val size = minOf(3, count)
            repeat(size) { accepted.add(data[offset + it]) }
            size
        }
        capture.finish()
        val output = ByteArrayOutputStream()
        val report = capture.exportF32le(output)
        val buffer = ByteBuffer.wrap(output.toByteArray()).order(ByteOrder.LITTLE_ENDIAN)
        val decoded = FloatArray(11) { buffer.getFloat() }
        assertArrayEquals(input, accepted.toFloatArray(), 0f)
        assertArrayEquals(input, decoded, 0f)
        assertEquals(44, output.size())
        assertEquals(11L, report.requestedFrames)
        assertEquals(11L, report.acceptedFrames)
        assertFalse(report.fullWindow)
        assertTrue(report.toJson().contains("\"input_binding\":\"UNBOUND\""))
    }

    @Test
    fun full_window_requires_all_30_seconds_of_accepted_pcm() {
        val frames = S13ReviewContract.TOTAL_FRAMES
        val complete = S13PcmCaptureReport(frames.toLong(), frames.toLong(),
            frames, frames, false, false, "sha")
        val short = S13PcmCaptureReport(11, 11, 11, 11, false, false, "sha")
        assertTrue(complete.fullWindow)
        assertFalse(short.fullWindow)
    }

    @Test
    fun matched_trace_capture_keeps_vehicle_trace_and_bank_identity() {
        val binding = S13CaptureBinding(
            "c63_w204_v6", "29b50961d9628f835e7172b797380ccb36a7f38d",
            "a".repeat(64), "b".repeat(64), "c".repeat(64),
        )
        val capture = BoundedPcmCapture(2, binding,
            "POST_ENVELOPES_PRE_AUDIOTRACK_SUBMISSION")
        writeAllPcm(floatArrayOf(0.1f, 0.2f), capture) { _, _, count -> count }
        capture.finish()
        val report = capture.exportF32le(ByteArrayOutputStream())
        val json = report.toJson()
        assertTrue(json.contains("\"input_binding\":\"MATCHED_TRACE\""))
        assertTrue(json.contains("\"vehicle_key\":\"c63_w204_v6\""))
        assertTrue(json.contains(binding.traceSha256))
        assertTrue(json.contains(binding.bankManifestSha256))
        assertTrue(json.contains(binding.eventScheduleSha256))
        assertTrue(json.contains("POST_ENVELOPES_PRE_AUDIOTRACK_SUBMISSION"))
    }

    @Test
    fun zero_negative_and_oversized_returns_fail_without_looping() {
        for (result in intArrayOf(0, -6, 3)) {
            var calls = 0
            rejectsWrite {
                writeAllPcm(floatArrayOf(0.1f, 0.2f)) { _, _, _ ->
                    calls++
                    result
                }
            }
            assertEquals(1, calls)
        }
    }

    @Test
    fun failed_partial_write_exports_a_marked_incomplete_prefix() {
        val capture = BoundedPcmCapture(5)
        var calls = 0
        rejectsWrite {
            writeAllPcm(FloatArray(5) { 0.2f }, capture) { _, _, _ ->
                if (calls++ == 0) 2 else -6
            }
        }
        capture.finish()
        val output = ByteArrayOutputStream()
        val report = capture.exportF32le(output)
        assertEquals(5L, report.requestedFrames)
        assertEquals(2L, report.acceptedFrames)
        assertEquals(2, report.capturedFrames)
        assertEquals(8, output.size())
        assertTrue(report.failed)
        assertFalse(report.fullWindow)
    }

    @Test
    fun capture_capacity_is_bounded_and_overflow_is_not_a_pass() {
        val capture = BoundedPcmCapture(4)
        writeAllPcm(FloatArray(9) { 0.1f }, capture) { _, _, count -> count }
        capture.finish()
        val output = ByteArrayOutputStream()
        val report = capture.exportF32le(output)
        assertEquals(9L, report.acceptedFrames)
        assertEquals(4, report.capturedFrames)
        assertEquals(16, output.size())
        assertTrue(report.overflow)
        assertFalse(report.fullWindow)
    }

    @Test
    fun nonfinite_pcm_is_never_submitted_to_the_writer() {
        var calls = 0
        try {
            writeAllPcm(floatArrayOf(Float.NaN)) { _, _, count -> calls++; count }
            fail("Expected non-finite rejection")
        } catch (_: IllegalArgumentException) {
            assertEquals(0, calls)
        }
    }
}
