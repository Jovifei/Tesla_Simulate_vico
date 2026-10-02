package com.vico.simulator.sound

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import kotlin.math.abs

class MatlabStatefulBankRendererTest {

    @Test
    fun stateful_renderer_is_present_for_continuous_mobile_playback() {
        val renderer = runCatching {
            Class.forName("com.vico.simulator.sound.MatlabStatefulBankRenderer")
        }.getOrNull()
        assertNotNull("S12 playback must use a stateful bank renderer", renderer)
    }

    @Test
    fun consecutive_blocks_keep_engine_phase_instead_of_restarting_the_loop() {
        val renderer = MatlabStatefulBankRenderer(testBank())
        val state = state()

        val first = renderer.render(state, 3)
        val second = renderer.render(state, 3)

        assertTrue("the second block must continue the phase", abs(first[0] - second[0]) > 0.0001f)
    }

    @Test
    fun shift_event_is_consumed_once_for_one_state_timestamp() {
        val renderer = MatlabStatefulBankRenderer(testBank(quiet = true, shift = floatArrayOf(0.40f, 0.25f, 0.10f)))
        val state = state().copy(timeS = 1.0, shiftTrigger = true)

        val event = renderer.render(state, 3)
        val repeated = renderer.render(state, 3)

        assertTrue(event.any { it > 0.09f })
        assertTrue(repeated.all { abs(it) < 0.0001f })
    }

    @Test
    fun afterfire_event_is_consumed_once_for_one_state_timestamp() {
        val renderer = MatlabStatefulBankRenderer(testBank(quiet = true, afterfire = floatArrayOf(0.30f, 0.20f, 0.10f)))
        val state = state().copy(timeS = 2.0, afterfireTrigger = true)

        val event = renderer.render(state, 3)
        val repeated = renderer.render(state, 3)

        assertTrue(event.any { it > 0.09f })
        assertTrue(repeated.all { abs(it) < 0.0001f })
    }

    @Test
    fun review_trace_cursor_contract_is_available() {
        val cursor = runCatching {
            Class.forName("com.vico.simulator.sound.S13TraceCursor")
        }.getOrNull()
        assertNotNull("S13 needs a frame-aligned review trace cursor", cursor)
    }

    @Test
    fun bounded_pcm_capture_contract_is_available() {
        val capture = runCatching {
            Class.forName("com.vico.simulator.sound.BoundedPcmCapture")
        }.getOrNull()
        assertNotNull("S13 needs opt-in bounded digital PCM capture", capture)
    }

    @Test
    fun review_package_loader_is_available_for_the_verified_sidecar() {
        val loader = runCatching {
            Class.forName("com.vico.simulator.sound.S13ReviewPackageLoader")
        }.getOrNull()
        assertNotNull("S13 needs a fail-closed sidecar and trace loader", loader)
    }

    @Test
    fun review_renderer_exposes_explicit_frame_scheduled_event_api() {
        val method = runCatching {
            MatlabStatefulBankRenderer::class.java.getMethod(
                "renderReview",
                SoundState::class.java,
                SoundState::class.java,
                Int::class.javaPrimitiveType,
                Int::class.javaPrimitiveType,
                List::class.java,
            )
        }.getOrNull()
        assertNotNull("S13 review events must be scheduled by absolute audio frame", method)
    }

    @Test
    fun same_trace_review_session_is_available() {
        val session = runCatching {
            Class.forName("com.vico.simulator.sound.S13ReviewSession")
        }.getOrNull()
        assertNotNull("S13 needs a deterministic same-trace playback session", session)
    }

    @Test
    fun nonfinite_transient_mix_is_rejected_before_playback() {
        val renderer = MatlabStatefulBankRenderer(
            testBank(quiet = true, afterfire = floatArrayOf(Float.NaN)),
        )
        val result = runCatching {
            renderer.render(state().copy(timeS = 3.0, afterfireTrigger = true), 1)
        }
        assertTrue("non-finite PCM must not be returned to AudioTrack", result.isFailure)
        assertTrue(result.exceptionOrNull() is IllegalStateException)
    }

    @Test
    fun normal_finite_loop_keeps_the_existing_sample_sequence() {
        val renderer = MatlabStatefulBankRenderer(testBank())
        val cycle = floatArrayOf(0f, 0.1f, 0.2f, 0.3f, 0.2f, 0.1f, 0f, -0.1f)
        val expected = FloatArray(24) { cycle[it % cycle.size] }
        val first = renderer.render(state(), 7)
        val rest = renderer.render(state(), 17)
        assertArrayEquals(expected, first + rest, 1e-6f)
        assertTrue(renderer.mixStats().hardClipFrames == 0L)
        renderer.reset()
        assertTrue(renderer.mixStats().evaluatedFrames == 0L)
        assertArrayEquals(expected, renderer.render(state(), 24), 1e-6f)
    }

    @Test
    fun reports_preclip_overload_without_removing_playback_safety() {
        val renderer = MatlabStatefulBankRenderer(testBank(
            quiet = true,
            afterfire = FloatArray(8) { 0.8f },
            shift = FloatArray(8) { 0.8f },
        ))
        val output = renderer.render(
            state().copy(timeS = 1.0, afterfireTrigger = true, shiftTrigger = true), 8,
        )
        assertTrue(output.all { it == 1f })
        val stats = renderer.mixStats()
        assertTrue(stats.preClipPeak > 1.59)
        assertTrue(stats.aboveContractFrames == 8L)
        assertTrue(stats.hardClipFrames == 8L)
        assertTrue(stats.nonFiniteFrames == 0L)
    }

    @Test
    fun reports_requested_load_and_rpm_outside_bank() {
        val renderer = MatlabStatefulBankRenderer(testBank())
        renderer.render(state().copy(load = 0.14, rpm = 900.0), 960)
        assertTrue(renderer.mixStats().loadOutOfBankFrames == 960L)
        assertTrue(renderer.mixStats().rpmOutOfBankFrames == 960L)
    }

    @Test
    fun nonfinite_mix_is_reported_and_not_returned_as_audio() {
        val renderer = MatlabStatefulBankRenderer(testBank(
            quiet = true, afterfire = floatArrayOf(Float.NaN),
        ))
        try {
            renderer.render(state().copy(afterfireTrigger = true), 1)
            fail("Expected non-finite mix rejection")
        } catch (_: IllegalStateException) {
            assertTrue(renderer.mixStats().nonFiniteFrames == 1L)
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun nonfinite_control_state_is_rejected_before_phase_updates() {
        MatlabStatefulBankRenderer(testBank()).render(state().copy(rpm = Double.NaN), 1)
    }

    @Test
    fun review_events_start_at_crop_frame_and_match_across_block_partitions() {
        val bank = testBank(quiet = true, shift = floatArrayOf(0.4f, 0.25f, 0.1f))
        val traceBytes = "trace-fixture".toByteArray()
        val eventBytes = byteArrayOf(4, 5, 6)
        val binding = S13EventBinding(
            id = "shift_event_01",
            kind = "shift",
            assetPath = "s12_v10/test/shift",
            assetSha256 = S13ReviewContract.sha256(eventBytes),
            traceSha256 = S13ReviewContract.sha256(traceBytes),
            sourceDomain = "TRACE_EVENT",
            sourceTimeS = 501.0 / 48_000,
            sourceFrame = 501,
            cropStartFrame = 500,
            triggerOffsetFrames = 1,
            sampleCount = 3,
        ).validate(traceBytes, eventBytes, 3)

        val start = state().copy(rpm = 1000.0, load = 0.3)
        val middle = state().copy(timeS = 0.01, rpm = 1500.0, load = 0.6)
        val end = state().copy(timeS = 0.02, rpm = 2000.0, load = 0.9)
        val wholeRenderer = MatlabStatefulBankRenderer(bank)
        val whole = wholeRenderer.renderReview(start, end, 0, 960, listOf(binding))

        val splitRenderer = MatlabStatefulBankRenderer(bank)
        val first = splitRenderer.renderReview(start, middle, 0, 480, emptyList())
        val second = splitRenderer.renderReview(middle, end, 480, 480, listOf(binding))
        val split = first + second

        assertArrayEquals(whole, split, 1e-5f)
        assertEquals(0f, whole[499], 0f)
        assertEquals(0.4f, whole[500], 1e-6f)
        assertEquals(0.25f, whole[501], 1e-6f)
        assertEquals(0.1f, whole[502], 1e-6f)
        assertEquals(0f, whole[503], 0f)
    }

    @Test
    fun rpm_blend_diagnostic_is_block_partition_invariant_for_a_dynamic_trace() {
        val bank = testBank()
        val start = state().copy(rpm = 1000.0, load = 0.3, shiftGain = 0.9)
        val middle = state().copy(timeS = 0.01, rpm = 1500.0, load = 0.6, shiftGain = 0.95)
        val end = state().copy(timeS = 0.02, rpm = 2000.0, load = 0.9, shiftGain = 1.0)

        val wholeCapture = S13RpmBlendCapture(960)
        val wholeRenderer = MatlabStatefulBankRenderer(bank)
        wholeRenderer.enableRpmBlendCapture(wholeCapture)
        val whole = wholeRenderer.renderReview(start, end, 0, 960, emptyList())

        val splitCapture = S13RpmBlendCapture(960)
        val splitRenderer = MatlabStatefulBankRenderer(bank)
        splitRenderer.enableRpmBlendCapture(splitCapture)
        val first = splitRenderer.renderReview(start, middle, 0, 480, emptyList())
        val second = splitRenderer.renderReview(middle, end, 480, 480, emptyList())

        assertArrayEquals(whole, first + second, 1e-5f)
        assertEquals(960, wholeCapture.frameCount)
        assertEquals(960, splitCapture.frameCount)
        assertArrayEquals(wholeCapture.lowerPath, splitCapture.lowerPath, 1e-6f)
        assertArrayEquals(wholeCapture.upperPath, splitCapture.upperPath, 1e-6f)
        assertArrayEquals(wholeCapture.rpmWeight, splitCapture.rpmWeight, 1e-6f)
        assertArrayEquals(wholeCapture.sharedGain, splitCapture.sharedGain, 1e-6f)
        assertArrayEquals(wholeCapture.eventContribution, splitCapture.eventContribution, 1e-6f)
        assertArrayEquals(wholeCapture.rpmLowerIndex, splitCapture.rpmLowerIndex)
        assertArrayEquals(wholeCapture.rpmUpperIndex, splitCapture.rpmUpperIndex)
        assertTrue(wholeCapture.rpmWeight.any { it in 0.2f..0.8f })
    }

    private fun state() = SoundState(
        timeS = 0.0,
        rpm = 1000.0,
        frequencyHz = 1.0,
        amplitude = 1.0,
        brightness = 1.0,
        harmonics = floatArrayOf(),
        muted = false,
        load = 0.3,
        shiftGain = 1.0,
    )

    private fun testBank(
        quiet: Boolean = false,
        afterfire: FloatArray = floatArrayOf(),
        shift: FloatArray = floatArrayOf(),
    ): MatlabSoundBank {
        val samples = if (quiet) FloatArray(8) else floatArrayOf(0.0f, 0.10f, 0.20f, 0.30f, 0.20f, 0.10f, 0.0f, -0.10f)
        val loops = listOf(
            MatlabLoop(1000.0, 0.3, samples),
            MatlabLoop(1000.0, 0.9, samples),
            MatlabLoop(2000.0, 0.3, samples),
            MatlabLoop(2000.0, 0.9, samples),
        )
        return MatlabSoundBank(
            vehicleKey = "test",
            sampleRateHz = 48000,
            powertrain = MatlabPowertrainSpec(
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
            ),
            loops = loops,
            afterfire = afterfire,
            shiftEvents = if (shift.isEmpty()) emptyList() else listOf(MatlabTransient("shift", shift)),
        )
    }
}
