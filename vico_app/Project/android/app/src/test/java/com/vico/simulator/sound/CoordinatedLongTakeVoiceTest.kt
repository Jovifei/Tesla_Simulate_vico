package com.vico.simulator.sound

import java.security.MessageDigest
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin

/** HC-C1 only synthetic sine + long modulation, NO restricted recordings. */
class CoordinatedLongTakeVoiceTest {
    private fun evidence() = CoordinatedLongTakeVoice.Evidence(
        sourceClass = "SYNTHETIC_TEST_ONLY",
        licenseGate = "NOT_DISTRIBUTABLE_TEST",
        captureState = "SYNTHETIC_KNOWN_RPM_LOAD",
        phaseState = "SYNTHETIC_KNOWN_720",
        holdoutState = "SYNTHETIC_INDEPENDENT_GROUP",
    )

    private fun sha(samples: FloatArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        for (v in samples) {
            val bits = v.toRawBits()
            for (i in 0..3) digest.update((bits ushr (i * 8)).toByte())
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
    private fun take(): CoordinatedLongTakeVoice.Take {
        val part = 96_000
        val pcm = FloatArray(part * 2)
        val cfg = listOf(Triple(16, .12, 960.0), Triple(25, .20, 1500.0))
        for (c in cfg.indices) {
            val (cycles, volume, _) = cfg[c]
            for (i in 0 until part) {
                val phase = i.toDouble() * cycles / part
                pcm[c * part + i] = (volume * sin(2 * PI * phase) +
                    .022 * sin(2 * PI * phase / cycles) +
                    .018 * sin(4 * PI * phase)).toFloat()
            }
        }
        return CoordinatedLongTakeVoice.Take(
            vehicleKey = "hellcat_v6", sampleRate = 48000,
            takeId = "synthetic-hellcat-test-v1", samples = pcm,
            pcmSha256 = sha(pcm), evidence = evidence(),
            regions = listOf(
                CoordinatedLongTakeVoice.Region("low_rpm", 0, part, 16, 960.0, .3),
                CoordinatedLongTakeVoice.Region("high_rpm", part, part * 2, 25, 1500.0, .8),
            ),
        )
    }
    private fun voice() = CoordinatedLongTakeVoice.prepare(take())
    private fun state(rpm: Double = 960.0, load: Double = .3) = SoundState(
        timeS = 1.0, rpm = rpm, frequencyHz = 45.0, amplitude = .3,
        brightness = .3, harmonics = floatArrayOf(), muted = false, load = load,
        inputControl = DriveInputControl(DriveInputSource.DEMO, 7L, Long.MAX_VALUE, true, true),
    )
    private fun bank(quiet: Boolean = true, sampleRate: Int = 48000) = MatlabSoundBank(
        vehicleKey = "hellcat_v6", sampleRateHz = sampleRate,
        powertrain = MatlabPowertrainSpec(
            idleRpm = 960.0, redlineRpm = 7000.0,
            gearRatios = doubleArrayOf(3.0, 2.0), finalDrive = 3.0,
            wheelRadiusM = .3, launchRpm = 1500.0, shiftRpm = 6000.0,
            shiftAttackS = .018, shiftHoldS = .032,
            shiftRecoveryS = .075, shiftSettleS = .055,
            shiftMinTorque = .22, shiftReengageGain = 1.08,
            minimumShiftIntervalS = .35, downshiftRatio = .68,
            speedCeilingKmh = 144.0,
        ),
        loops = listOf(
            MatlabLoop(960.0, .3, FloatArray(8) { if (quiet) 0f else .08f }),
            MatlabLoop(960.0, .8, FloatArray(8)),
            MatlabLoop(1500.0, .3, FloatArray(8)),
            MatlabLoop(1500.0, .8, FloatArray(8)),
        ),
        afterfire = floatArrayOf(.3f, -.2f, .1f),
        shiftEvents = listOf(MatlabTransient("shift", floatArrayOf(.2f, -.1f, .04f))),
    )

    private fun normal(): MatlabStatefulBankRenderer = MatlabStatefulBankRenderer(
        bank(), LoopTraversalMode.NORMAL_SEAM_ENVELOPE_V1, "hellcat_original_bank_unchanged",
    )

    @Test fun recordedTakeRejectsUnalignedStatesCorruptHashIllegalEvidenceAndSourcePeak() {
        val t = take()
        assertEquals("SYNTHETIC_TEST_ONLY", voice().snapshot().sourceClass)
        assertThrows(IllegalArgumentException::class.java) {
            CoordinatedLongTakeVoice.prepare(t.copy(pcmSha256 = "0".repeat(64)))
        }
        assertThrows(IllegalArgumentException::class.java) {
            CoordinatedLongTakeVoice.prepare(t.copy(
                evidence = evidence().copy(licenseGate = "PRODUCT_DISTRIBUTION_CLEARED"),
            ))
        }
        assertThrows(IllegalArgumentException::class.java) {
            CoordinatedLongTakeVoice.prepare(t.copy(
                regions = t.regions.mapIndexed { i, r -> if (i == 1) r.copy(cycles720 = 16) else r },
            ))
        }
        assertThrows(IllegalArgumentException::class.java) {
            CoordinatedLongTakeVoice.prepare(t.copy(
                samples = t.samples.clone().also { it[90_000] = .9f },
            ))
        }
        assertThrows(IllegalArgumentException::class.java) {
            CoordinatedLongTakeVoice.prepare(t.copy(
                regions = t.regions.mapIndexed { i, r -> if (i == 1) r.copy(startFrame = 100) else r },
            ))
        }
    }

    @Test fun synchronizedPhaseAndSyntheticPCMRemainPartitionInvariantAndFinite() {
        val whole = voice().also { it.setControl(960.0, .3) }
        val parts = voice().also { it.setControl(960.0, .3) }
        val expected = FloatArray(40_000) { whole.next() }
        val actual = FloatArray(40_000)
        var at = 0
        var choice = 0
        val chunks = intArrayOf(1, 17, 128, 960, 997)
        while (at < actual.size) {
            val n = minOf(actual.size - at, chunks[choice++ % chunks.size])
            repeat(n) { actual[at++] = parts.next() }
        }
        assertArrayEquals(expected, actual, 0f)
        assertEquals(whole.snapshot().phaseCycles720, parts.snapshot().phaseCycles720, 0.0)
        assertTrue(expected.all { it.isFinite() && abs(it) < .55f })
    }

    @Test fun switchesAcrossSharedPhaseDoNotResetReadheadOrProduceSyntheticClick() {
        val a = voice()
        a.setControl(960.0, .3)
        var last = a.next()
        var jump = 0.0
        repeat(65_000) { i ->
            if (i == 16_000) a.setControl(1500.0, .8)
            if (i == 45_000) a.setControl(960.0, .3)
            val now = a.next()
            jump = maxOf(jump, abs(now - last).toDouble())
            last = now
        }
        assertEquals(2, a.snapshot().switches)
        assertEquals("low_rpm", a.snapshot().activeRegion)
        assertTrue("Unexpected synthetic transition jump: $jump", jump < .03)
        assertEquals(0, a.snapshot().nonfinite)
    }

    @Test fun nativeRendererActuallyMixesExperimentalContinuousAndOriginalEventsOnce() {
        val voice = voice()
        val r = normal()
        r.installCoordinatedVoiceForReview(voice)
        val x = r.render(state(), 960)
        assertTrue(x.any { abs(it) > .01f })
        assertEquals(960L, voice.snapshot().renderedFrames)
        val event = state().copy(timeS = 5.0, afterfireTrigger = true, shiftTrigger = true)
        val first = r.render(event, 1)
        val second = r.render(event, 1)
        assertTrue(first[0].isFinite() && second[0].isFinite())
        assertTrue(abs(first[0] - second[0]) > .10f)
        val stats = r.mixStats()
        assertEquals(0L, stats.nonFiniteFrames)
        assertEquals(0L, stats.hardClipFrames)
        assertTrue(stats.preClipPeak < .8413951416451951)
    }

    @Test fun cannotInstallAfterRunningOrOnLegacyOrAlternateVehicle() {
        val v = voice()
        assertThrows(IllegalArgumentException::class.java) {
            MatlabStatefulBankRenderer(bank()).installCoordinatedVoiceForReview(v)
        }
        val r = normal()
        r.render(state(), 960)
        assertThrows(IllegalArgumentException::class.java) {
            r.installCoordinatedVoiceForReview(v)
        }
    }

    @Test fun candidateRequiresMatchingInternalRendererRateWithoutRestrictingOrdinaryBanks() {
        val mismatched = MatlabStatefulBankRenderer(
            bank(sampleRate = 96000), LoopTraversalMode.NORMAL_SEAM_ENVELOPE_V1,
            "hellcat_original_bank_unchanged",
        )
        assertThrows(IllegalArgumentException::class.java) {
            mismatched.installCoordinatedVoiceForReview(voice())
        }
        assertEquals(null, mismatched.coordinatedVoiceSnapshot())
        assertTrue(mismatched.render(state(), 960).all { it.isFinite() })
        val matched = normal()
        val candidate = voice()
        matched.installCoordinatedVoiceForReview(candidate)
        matched.render(state(), 4800)
        assertEquals(4800L, candidate.snapshot().renderedFrames)
        assertEquals(0.8, candidate.snapshot().phaseCycles720, 1e-10)
    }

    @Test fun muteWrongInputAndResetCancelUntilNewPreparedSession() {
        val v = voice()
        val r = normal()
        r.installCoordinatedVoiceForReview(v)
        r.render(state(), 400)
        val invalid = state().copy(inputControl = DriveInputControl(
            DriveInputSource.REAL, 8L, Long.MAX_VALUE, true, true,
        ))
        val muted = r.render(invalid, 128)
        assertTrue(muted.all { it == 0f })
        assertTrue(v.snapshot().cancelled)
        val returned = r.render(state(), 128)
        assertTrue(returned.all { it == 0f })
        r.reset()
        assertEquals(null, r.coordinatedVoiceSnapshot())
        assertTrue(r.render(state(), 128).all { it.isFinite() })
    }

    @Test fun oldDefaultRendererWithoutInstallIsBitIdenticalAcrossSessions() {
        val a = normal()
        val b = normal()
        val s = state()
        assertArrayEquals(a.render(s, 12_000), b.render(s, 12_000), 0f)
        assertEquals(null, a.coordinatedVoiceSnapshot())
    }
}
