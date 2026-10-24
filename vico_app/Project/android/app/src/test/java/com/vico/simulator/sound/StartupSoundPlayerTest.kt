package com.vico.simulator.sound

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class StartupSoundPlayerTest {
    private val assetRoot = sequenceOf(File("src/main/assets/startup/hellcat"), File("app/src/main/assets/startup/hellcat"))
        .first { it.isDirectory }
    private fun bytes(name: String) = File(assetRoot, name).readBytes()
    private fun player() = StartupSoundPlayer.fromValidatedAsset(bytes("hellcat-startup.wav"),
        bytes("manifest.json"), bytes("ATTRIBUTION.txt"), 48000).also { it.resetSession(allowDemoStartup = true) }
    private fun state() = SoundState(0.0, 700.0, 46.0, .3, .2, floatArrayOf(), false,
        inputControl = DriveInputControl(DriveInputSource.DEMO, 7L, Long.MAX_VALUE, true, true),
        modelSpeedKmh = 0.0)
    private fun block(p: StartupSoundPlayer, count: Int, state: SoundState = state(), allow: Boolean = true,
        vehicle: String = "hellcat_v6") = FloatArray(count) { .2f }.also {
        p.mixInto(it, state, allow, vehicle)
    }

    @Test fun normalModelHasAnExplicitOptInStartupGate() {
        assertTrue("Native normal playback has no explicit startup gate",
            MatlabV6SoundBankEngine::class.java.methods.any {
                it.name == "renderState" && it.parameterTypes.size == 3 &&
                    it.parameterTypes[2] == Boolean::class.javaPrimitiveType
            })
    }

    @Test fun actualPackHasAudioClockFadeAndExactIdleHandoffOncePerSession() {
        val pcm = FloatWavDecoder.decode(bytes("hellcat-startup.wav")).samples
        val p = player()
        val output = block(p, pcm.size + 100)
        assertEquals(0f, output[0], 0f)
        assertEquals(pcm[1000], output[1000], 0f)
        assertEquals(.2f, output[pcm.lastIndex], 0f)
        assertEquals(.2f, output.last(), 0f)
        assertEquals("ENDED", p.snapshot().stage)
        assertEquals(pcm.size.toLong(), p.snapshot().renderedFrames)
        assertArrayEquals(FloatArray(960) { .2f }, block(p, 960), 0f)
        assertEquals("STARTUP_IDLE_CROSSFADE_PRE_APP_ENVELOPES", p.snapshot().domain)
        p.resetSession(allowDemoStartup = true)
        assertEquals(0f, block(p, 1)[0], 0f)
        assertEquals("PLAYING", p.snapshot().stage)
    }

    @Test fun arbitraryPartitionsAreBitExactAndDoNotAllocatePerSampleResults() {
        val total = StartupSoundPlayer.FRAMES + 73
        val whole = block(player(), total)
        val split = player()
        val parts = ArrayList<Float>()
        var remaining = total
        var i = 0
        val sizes = intArrayOf(1, 17, 128, 960, 1024, 4093)
        while (remaining > 0) {
            val n = minOf(remaining, sizes[i++ % sizes.size])
            block(split, n).forEach { parts.add(it) }
            remaining -= n
        }
        assertArrayEquals(whole, parts.toFloatArray(), 0f)
        assertEquals(StartupSoundPlayer.FRAMES.toLong(), split.snapshot().renderedFrames)
    }

    @Test fun muteSourceUnknownSpeedMovingAndGlobalGateConsumePendingSession() {
        val s = state()
        val input = requireNotNull(s.inputControl)
        val invalid = listOf(s.copy(muted = true), s.copy(inputControl = null),
            s.copy(inputControl = input.copy(source = DriveInputSource.REAL)),
            s.copy(inputControl = input.copy(source = DriveInputSource.QUALIFICATION)),
            s.copy(inputControl = input.copy(source = DriveInputSource.PREVIEW)),
            s.copy(inputControl = input.copy(speedUsable = false)),
            s.copy(modelSpeedKmh = null), s.copy(modelSpeedKmh = Double.NaN), s.copy(modelSpeedKmh = 1.01))
        invalid.forEach { rejectedState ->
            val p = player()
            assertArrayEquals(FloatArray(32) { .2f }, block(p, 32, rejectedState), 0f)
            assertArrayEquals(FloatArray(32) { .2f }, block(p, 32), 0f)
            assertEquals("CANCELLED", p.snapshot().stage)
            assertEquals(0L, p.snapshot().renderedFrames)
        }
        val gated = player()
        assertArrayEquals(FloatArray(32) { .2f }, block(gated, 32, allow = false), 0f)
        assertArrayEquals(FloatArray(32) { .2f }, block(gated, 32), 0f)
        assertArrayEquals(FloatArray(32) { .2f }, block(player(), 32, vehicle = "c63_w204_v6"), 0f)
    }

    @Test fun cancelWhilePlayingCannotResumeOnUnmuteNewEpochOrStandingStill() {
        for (change in 0..4) {
            val p = player()
            block(p, 960)
            val next = when (change) {
                0 -> state().copy(muted = true)
                1 -> state().copy(modelSpeedKmh = 2.0)
                2 -> state().copy(inputControl = state().inputControl!!.copy(epoch = 8L))
                3 -> state().copy(inputControl = state().inputControl!!.copy(source = DriveInputSource.REAL))
                else -> state()
            }
            assertArrayEquals(FloatArray(128) { .2f }, block(p, 128, next, allow = change != 4), 0f)
            assertArrayEquals(FloatArray(128) { .2f }, block(p, 128), 0f)
            assertEquals(960L, p.snapshot().renderedFrames)
        }
    }

    @Test fun firstInputGateClearDoesNotConsumeFreshArmButActiveClearDoes() {
        val p = player()
        p.cancelActive()
        assertEquals("ARMED", p.snapshot().stage)
        block(p, 32)
        p.cancelActive()
        assertArrayEquals(FloatArray(32) { .2f }, block(p, 32), 0f)
        p.resetSession(allowDemoStartup = true)
        p.cancelActive()
        assertEquals(0f, block(p, 1)[0], 0f)
    }

    @Test fun unspecifiedSessionCannotCarryPendingArmThroughInvalidRealIntoDemo() {
        val p = player()
        p.resetSession() // A REAL/unknown preparation has no explicit DEMO startup request.
        p.cancelActive() // First invalid REAL writer block never calls mixInto.
        assertArrayEquals(FloatArray(960) { .2f }, block(p, 960), 0f)
        assertEquals(0L, p.snapshot().renderedFrames)
    }

    @Test fun invalidIdentityManifestAttributionRateOrWaveBytesFailClosed() {
        val wav = bytes("hellcat-startup.wav")
        val manifest = bytes("manifest.json")
        val credit = bytes("ATTRIBUTION.txt")
        assertThrows(IllegalArgumentException::class.java) { StartupSoundPlayer.fromValidatedAsset(wav, manifest, credit, 96000) }
        assertThrows(IllegalArgumentException::class.java) { StartupSoundPlayer.fromValidatedAsset(wav.copyOf().also { it[50] = (it[50].toInt() xor 1).toByte() }, manifest, credit, 48000) }
        assertThrows(IllegalArgumentException::class.java) { StartupSoundPlayer.fromValidatedAsset(wav, manifest + 32.toByte(), credit, 48000) }
        assertThrows(IllegalArgumentException::class.java) { StartupSoundPlayer.fromValidatedAsset(wav, manifest, byteArrayOf(), 48000) }
        val p = StartupSoundPlayer.fromValidatedAsset(wav, manifest, credit, 48000)
        wav.fill(0)
        p.resetSession(allowDemoStartup = true)
        assertTrue(block(p, 1000).any { it != .2f })
    }

    @Test fun missingAssetNeverInventsStarterOrChangesLegacyContinuousPcm() {
        val p = StartupSoundPlayer.unavailable("no-validated-pack")
        p.resetSession()
        assertArrayEquals(FloatArray(960) { .2f }, block(p, 960), 0f)
        assertEquals("UNAVAILABLE", p.snapshot().stage)
        assertFalse(p.snapshot().available)
        assertEquals("no-validated-pack", p.snapshot().reason)
    }
}
