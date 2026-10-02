package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume
import org.junit.Test

/**
 * Explicit local reference export. A skipped invocation is a tool not-run, never a qualification pass.
 */
class N2PcmFixtureTest {
    @Test
    fun exportSixControlledBranchesForLocalReferenceComputation() {
        val destination = System.getenv("VICO_C63_N2_FIXTURE_OUTPUT")
        Assume.assumeTrue(!destination.isNullOrBlank())
        val root = File(requireNotNull(destination))
        assertFalse(File(root, "manifest.tsv").exists())
        root.mkdirs()

        fun point(n: Int): SoundState {
            val phase = n % 151
            val closed = phase in 100..125
            return SoundState(
                timeS = n * .02,
                rpm = if (closed) 4000.0 else 5000.0,
                frequencyHz = 0.0,
                amplitude = if (closed) .05 else .9,
                brightness = .9,
                harmonics = floatArrayOf(),
                muted = false,
                throttle = if (closed) .05 else .9,
                load = if (closed) .05 else .9,
                shiftTrigger = phase == 90,
            )
        }

        val profile = N2Profile.preregistered()
        val trajectory = (0 until 604).map(::point)
        val exports = N2QualificationExport.renderAll(
            trajectory,
            HybridTestProfiles.create(),
            profile,
        )
        val rows = mutableListOf("candidate\tmode\tevents_audible\tframes\tprofile_identity\trms\tpeak")
        exports.forEach { result ->
            val suffix = if (result.eventsAudible) "on" else "off"
            val file = File(root, result.mode.name.lowercase() + "_event_" + suffix + ".f32le")
            file.outputStream().buffered(65536).use { out ->
                val bytes = ByteBuffer.allocate(960 * 4).order(ByteOrder.LITTLE_ENDIAN)
                var offset = 0
                while (offset < result.pcm.size) {
                    bytes.clear()
                    val count = minOf(960, result.pcm.size - offset)
                    repeat(count) { bytes.putFloat(result.pcm[offset + it]) }
                    out.write(bytes.array(), 0, count * 4)
                    offset += count
                }
            }
            assertTrue(file.length() == result.frames.toLong() * 4L)
            rows += listOf(
                result.candidateId,
                result.mode.name,
                result.eventsAudible.toString(),
                result.frames.toString(),
                profile.identity,
                result.measurement.rms.toString(),
                result.measurement.peak.toString(),
            ).joinToString("\t")
        }
        File(root, "manifest.tsv").writeText(rows.joinToString("\n") + "\n")
    }
}
