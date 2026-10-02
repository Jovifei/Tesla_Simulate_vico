package com.vico.simulator.sound

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class S13ReviewSessionTest {
    private fun event(
        traceBytes: ByteArray,
        fileBytes: ByteArray,
        id: String,
        kind: String,
        file: String,
        sourceFrame: Int,
        cropStartFrame: Int,
        sampleCount: Int,
        domain: String,
    ) = S13EventBinding(
        id = id,
        kind = kind,
        assetPath = "s12_v10/test/$file",
        assetSha256 = S13ReviewContract.sha256(fileBytes),
        traceSha256 = S13ReviewContract.sha256(traceBytes),
        sourceDomain = domain,
        sourceTimeS = sourceFrame.toDouble() / S13ReviewContract.SAMPLE_RATE,
        sourceFrame = sourceFrame,
        cropStartFrame = cropStartFrame,
        triggerOffsetFrames = sourceFrame - cropStartFrame,
        sampleCount = sampleCount,
    ).validate(traceBytes, fileBytes, sampleCount)

    private fun session(): S13ReviewSession {
        val traceBytes = "trace".toByteArray()
        val shiftBytes = byteArrayOf(1, 2, 3, 4)
        val afterfireBytes = byteArrayOf(5, 6)
        val points = List(S13ReviewContract.TRACE_POINTS) { index ->
            S13TracePoint(index / 50.0, 1000.0, 0.3, 0.2, 0.0)
        }
        val trace = S13TraceCursor(points)
        val events = listOf(
            event(traceBytes, shiftBytes, "shift_event_01", "shift", "shift.wav",
                102, 100, 4, "TRACE_EVENT"),
            event(traceBytes, afterfireBytes, "afterfire_tipout", "afterfire", "after.wav",
                864_267, 864_000, 300, "POST_PTR_STEM_ONSET"),
        )
        val spec = MatlabPowertrainSpec(
            idleRpm = 1000.0,
            redlineRpm = 2000.0,
            gearRatios = doubleArrayOf(3.0, 2.0),
            finalDrive = 3.0,
            wheelRadiusM = 0.3,
            launchRpm = 1500.0,
            shiftRpm = 1800.0,
            shiftAttackS = 0.018,
            shiftHoldS = 0.032,
            shiftRecoveryS = 0.075,
            shiftSettleS = 0.055,
            shiftMinTorque = 0.22,
            shiftReengageGain = 1.08,
            minimumShiftIntervalS = 0.35,
            downshiftRatio = 0.68,
            speedCeilingKmh = 144.0,
        )
        val bank = MatlabSoundBank(
            vehicleKey = "test",
            sampleRateHz = 48_000,
            powertrain = spec,
            loops = listOf(
                MatlabLoop(1000.0, 0.3, FloatArray(8)),
                MatlabLoop(1000.0, 0.9, FloatArray(8)),
                MatlabLoop(2000.0, 0.3, FloatArray(8)),
                MatlabLoop(2000.0, 0.9, FloatArray(8)),
            ),
            afterfire = FloatArray(300) { 0.2f },
            shiftEvents = listOf(MatlabTransient("shift.wav", floatArrayOf(0.4f, 0.3f, 0.2f, 0.1f)),
                MatlabTransient("other.wav", floatArrayOf(-0.5f))),
        )
        val review = S13ReviewPackage(
            vehicleKey = "test",
            sourceCommit = "29b50961d9628f835e7172b797380ccb36a7f38d",
            traceSha256 = S13ReviewContract.sha256(traceBytes),
            bankManifestSha256 = "a".repeat(64),
            fixedVehicleGain = 1.0,
            trace = trace,
            events = events,
        )
        return S13ReviewSession(bank, review)
    }

    @Test
    fun review_session_emits_exactly_one_half_open_thirty_second_window() {
        val session = session()
        val pcm = session.renderAll()
        assertEquals(S13ReviewContract.TOTAL_FRAMES, pcm.size)
        assertEquals(S13ReviewContract.TOTAL_FRAMES, session.framesRendered)
        assertTrue(session.isComplete)
        assertNull(session.renderNext())
        assertEquals(S13ReviewContract.TOTAL_FRAMES.toLong(), session.mixStats().evaluatedFrames)
        assertTrue(pcm.all { it.isFinite() })
    }

    @Test
    fun sourced_events_start_at_crop_frames_and_shift_identity_is_not_round_robin() {
        val pcm = session().renderAll()
        assertEquals(0.4f * 0.09f, pcm[100], 1e-6f)
        assertEquals(0.3f * 0.09f, pcm[101], 1e-6f)
        assertEquals(0.2f * 0.09f, pcm[102], 1e-6f)
        assertEquals(0.1f * 0.09f, pcm[103], 1e-6f)
        assertEquals(0f, pcm[104], 0f)
        assertEquals(0.2f, pcm[864_000], 1e-6f)
    }

    @Test
    fun identical_trace_bank_and_events_render_identical_pcm() {
        assertArrayEquals(session().renderAll(), session().renderAll(), 0f)
    }
}
