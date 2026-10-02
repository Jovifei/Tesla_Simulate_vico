package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class S13ReviewContractTest {
    private val traceBytes = "synthetic-trace-fixture".toByteArray(Charsets.UTF_8)
    private val assetBytes = byteArrayOf(1, 2, 3)

    private fun points() = List(S13ReviewContract.TRACE_POINTS) { index ->
        S13TracePoint(index / 50.0, 1000.0 + index, 0.2,
            0.1 + index / 2000.0, index.toDouble())
    }

    private fun rejects(block: () -> Unit) {
        try {
            block()
        } catch (_: IllegalArgumentException) {
            return
        }
        fail("Expected contract rejection")
    }

    private fun event(
        crop: Int? = 959,
        offset: Int? = 41,
        source: Int = 1000,
        frames: Int = 64,
    ) = S13EventBinding(
        id = "synthetic-shift-01",
        kind = "shift",
        assetPath = "shift.wav",
        assetSha256 = S13ReviewContract.sha256(assetBytes),
        traceSha256 = S13ReviewContract.sha256(traceBytes),
        sourceDomain = "TRACE_EVENT",
        sourceTimeS = source.toDouble() / S13ReviewContract.SAMPLE_RATE,
        sourceFrame = source,
        cropStartFrame = crop,
        triggerOffsetFrames = offset,
        sampleCount = frames,
    )

    @Test
    fun frame_domain_is_exactly_half_open_thirty_seconds() {
        val cursor = S13TraceCursor(points())
        assertEquals(1_440_000, S13ReviewContract.TOTAL_FRAMES)
        assertEquals(1000.0, cursor.at(0).rpm, 0.0)
        val last = cursor.at(1_439_999)
        assertEquals(1_439_999.0 / 48_000.0, last.timeS, 0.0)
        assertEquals(2499.0 + 959.0 / 960.0, last.rpm, 1e-9)
        rejects { cursor.at(-1) }
        rejects { cursor.at(1_440_000) }
    }

    @Test
    fun interpolation_is_linear_and_independent_of_block_partition() {
        val cursor = S13TraceCursor(points())
        assertEquals(1000.5, cursor.at(480).rpm, 1e-12)
        assertEquals(0.10025, cursor.at(480).throttle, 1e-12)
        assertEquals(0.5, cursor.at(480).accelerationMps2, 1e-12)
        assertEquals(1001.0, cursor.at(960).rpm, 0.0)
        val blocks = intArrayOf(96, 192, 240, 256, 480, 960)
        var frame = 0
        var block = 0
        while (frame < S13ReviewContract.TOTAL_FRAMES) {
            val count = minOf(blocks[block++ % blocks.size],
                S13ReviewContract.TOTAL_FRAMES - frame)
            val last = frame + count - 1
            assertEquals(1000.0 + last / 960.0, cursor.at(last).rpm, 1e-9)
            frame += count
        }
        assertEquals(S13ReviewContract.TOTAL_FRAMES, frame)
    }

    @Test
    fun malformed_trace_and_hash_are_rejected() {
        rejects { S13TraceCursor(points().dropLast(1)) }
        val wrongTime = points().toMutableList()
        wrongTime[50] = wrongTime[50].copy(timeS = 1.001)
        rejects { S13TraceCursor(wrongTime) }
        val nonFinite = points().toMutableList()
        nonFinite[50] = nonFinite[50].copy(rpm = Double.NaN)
        rejects { S13TraceCursor(nonFinite) }
        rejects { S13ReviewContract.requireSha256(byteArrayOf(9), event().assetSha256) }
    }

    @Test
    fun event_start_uses_crop_origin_not_trigger_time() {
        val first = event().validate(traceBytes, assetBytes, 64)
        assertEquals(959, first.startFrame)
        assertTrue(first.startsIn(0, 960))
        assertFalse(first.startsIn(960, 960))
        val second = event(crop = 960, offset = 40).validate(traceBytes, assetBytes, 64)
        assertFalse(second.startsIn(0, 960))
        assertTrue(second.startsIn(960, 960))
    }

    @Test
    fun missing_afterfire_origin_fails_closed() {
        rejects { event(crop = null).copy(kind = "afterfire").validate(traceBytes, assetBytes, 64) }
        rejects { event(offset = null).validate(traceBytes, assetBytes, 64) }
        rejects { event(offset = 40).validate(traceBytes, assetBytes, 64) }
        rejects { event().validate(traceBytes, assetBytes, 65) }
    }

    @Test
    fun source_exactly_at_first_decoded_frame_is_accepted() {
        val binding = event(crop = 959, offset = 0, source = 959, frames = 3)
        val placement = binding.validate(traceBytes, assetBytes, 3)
        assertEquals(959, placement.startFrame)
        assertEquals(binding, placement.binding)
    }

    @Test
    fun source_exactly_at_last_decoded_frame_is_accepted() {
        val binding = event(crop = 959, offset = 2, source = 961, frames = 3)
        val placement = binding.validate(traceBytes, assetBytes, 3)
        assertEquals(959, placement.startFrame)
        assertEquals(binding, placement.binding)
    }

    @Test
    fun source_at_first_frame_after_decoded_clip_is_rejected() {
        rejects {
            event(crop = 959, offset = 3, source = 962, frames = 3)
                .validate(traceBytes, assetBytes, 3)
        }
    }

    @Test
    fun original_outside_clip_fixture_is_rejected() {
        rejects { event(frames = 3).validate(traceBytes, assetBytes, 3) }
    }

    @Test
    fun negative_or_out_of_range_offset_fails_closed() {
        rejects {
            event(crop = 1002, offset = -2).copy(kind = "afterfire")
                .validate(traceBytes, assetBytes, 64)
        }
        rejects { event(offset = -1).validate(traceBytes, assetBytes, 64) }
        rejects { event(offset = 64).validate(traceBytes, assetBytes, 64) }
    }
}
