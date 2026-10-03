package com.vico.simulator.sound

import com.vico.simulator.sound.s18.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test

/** Post-freeze validation only: never fits, changes seeds, or alters source gain. */
class C63FrozenHybridValidationTest {
    @Test fun exportFrozenEventOffControls() {
        val profilePath = System.getenv("VICO_C63_FROZEN_HY1_PROFILE")
        val outputPath = System.getenv("VICO_C63_FROZEN_HY1_PAIR_OUTPUT")
        Assume.assumeTrue(!profilePath.isNullOrBlank() && !outputPath.isNullOrBlank())
        val profile = C63HybridProfile.fromBytes(File(requireNotNull(profilePath)).readBytes())
        assertEquals("3891836e55069d64392d84bee268e8974ba89558fa31f9c23ec95c375c65f294", profile.identity)
        val root = File(requireNotNull(outputPath))
        assertFalse(root.exists()); assertTrue(root.mkdirs())
        val baseline = C63HybridRenderer(profile, C63HybridMode.T, true, false)
        val event = C63HybridRenderer(profile, C63HybridMode.E, true, false)
        val bytes = ByteBuffer.allocate(960 * 4).order(ByteOrder.LITTLE_ENDIAN)
        File(root, "events_E_false.f32le").outputStream().buffered().use { stream ->
            repeat(604) { n ->
                val closed = n % 151 in 100..125
                val rpm = if (closed) 4000.0 else 5000.0
                val load = if (closed) .05 else .9
                val state = SoundState(n*.02, rpm, rpm/15, load, load, floatArrayOf(), false, load, load)
                val pcm = event.render(state, 960)
                assertArrayEquals(baseline.render(state, 960), pcm, 0f)
                bytes.clear(); pcm.forEach { bytes.putFloat(it) }; stream.write(bytes.array())
            }
        }
        assertFalse(event.eventObservation().truncated)
        assertTrue(event.peak <= .8413951416451951)
    }

    @Test fun exportActualFrozenFourBranchesAndEventOff() {
        val profilePath = System.getenv("VICO_C63_FROZEN_HY1_PROFILE")
        val outputPath = System.getenv("VICO_C63_FROZEN_HY1_VALIDATION")
        Assume.assumeTrue(!profilePath.isNullOrBlank() && !outputPath.isNullOrBlank())
        val profile = C63HybridProfile.fromBytes(File(requireNotNull(profilePath)).readBytes())
        assertEquals("3891836e55069d64392d84bee268e8974ba89558fa31f9c23ec95c375c65f294", profile.identity)
        val root = File(requireNotNull(outputPath))
        assertFalse("Never overwrite a validation run", root.exists())
        assertTrue(root.mkdirs())
        val rows = mutableListOf("case\tmode\tevents\tframes\tpeak\traw_arrivals\tdistinct_impulses\tpcm_sha256\tnumeric_pass")
        var numericPass = true
        fun state(t: Double, rpm: Double, load: Double) =
            SoundState(t, rpm, rpm / 15, load, load, floatArrayOf(), false, load, load)
        fun emit(id: String, mode: C63HybridMode, audible: Boolean, points: List<SoundState>) {
            val renderer = C63HybridRenderer(profile, mode, true, audible)
            val pcm = File(root, "${id}_${mode}_${audible}.f32le")
            val bytes = ByteBuffer.allocate(960 * 4).order(ByteOrder.LITTLE_ENDIAN)
            pcm.outputStream().buffered().use { stream ->
                for (point in points) {
                    bytes.clear()
                    for (sample in renderer.render(point, 960)) { assertTrue(sample.isFinite()); bytes.putFloat(sample) }
                    stream.write(bytes.array())
                }
            }
            val event = renderer.eventObservation()
            val pass = renderer.peak <= .8413951416451951
            numericPass = numericPass && pass
            val sha = java.security.MessageDigest.getInstance("SHA-256").digest(pcm.readBytes()).joinToString("") { "%02x".format(it) }
            rows += "$id\t$mode\t$audible\t${renderer.frames}\t${renderer.peak}\t${event.rawArrivals}\t${event.distinctImpulseFrames}\t$sha\t$pass"
            assertEquals(renderer.frames * 4, pcm.length())
        }
        val cases = linkedMapOf<String, List<SoundState>>()
        for (rpm in listOf(700.0,1400.0,2200.0,3200.0,4300.0,5500.0,6800.0,7200.0)) for (load in listOf(.32,.92)) {
            cases["steady_${rpm}_$load"] = (0 until 150).map { state(it*.02, rpm, load) }
        }
        cases["driven_ramp"] = (0 until 300).map { state(it*.02, 700+6500*it/299.0, .92) }
        cases["events"] = (0 until 604).map { n ->
            val closed = n % 151 in 100..125
            state(n*.02, if (closed) 4000.0 else 5000.0, if (closed) .05 else .9)
        }
        for ((id, points) in cases) {
            for (mode in C63HybridMode.values()) emit(id, mode, true, points)
            emit(id, C63HybridMode.SE, false, points)
        }
        File(root, "actual-kotlin.tsv").writeText(rows.joinToString("\n") + "\n")
        assertEquals(91, rows.size)
        assertTrue("Actual frozen HY1 exceeds the existing peak contract; inspect receipt", numericPass)
    }
}
