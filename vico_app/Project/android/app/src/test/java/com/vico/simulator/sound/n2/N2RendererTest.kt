package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.s18.C63HybridMode
import com.vico.simulator.sound.s18.C63HybridRenderer
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class N2RendererTest {
    private fun state(time: Double, closed: Boolean = false, shift: Boolean = false) = SoundState(
        timeS = time,
        rpm = if (closed) 4000.0 else 5000.0,
        frequencyHz = 0.0,
        amplitude = if (closed) .05 else .9,
        brightness = .9,
        harmonics = floatArrayOf(),
        muted = false,
        throttle = if (closed) .05 else .9,
        load = if (closed) .05 else .9,
        shiftTrigger = shift,
    )

    @Test
    fun textureControlIsExactlyTheFrozenTChain() {
        val baseline = HybridTestProfiles.create()
        val old = C63HybridRenderer(baseline, C63HybridMode.T, true, true)
        val fresh = N2Renderer(
            HybridTestProfiles.create(),
            N2Profile.preregistered(),
            N2Mode.T,
            qualificationOnly = true,
            eventsAudible = true,
        )
        repeat(80) { n ->
            val s = state(n * .02, n >= 60)
            assertArrayEquals(old.render(s, 960), fresh.render(s, 960), 0f)
        }
    }

    @Test
    fun one333960AndIrregularPartitionsProduceIdenticalPcm() {
        fun run(chunks: IntArray): FloatArray {
            val renderer = N2Renderer(
                HybridTestProfiles.create(),
                N2Profile.preregistered(),
                N2Mode.SE,
                qualificationOnly = true,
                eventsAudible = true,
            )
            val out = FloatArray(5760)
            var offset = 0
            var chunkIndex = 0
            while (offset < out.size) {
                val count = minOf(chunks[chunkIndex++ % chunks.size], out.size - offset)
                renderer.render(state(0.0), count).copyInto(out, offset)
                offset += count
            }
            return out
        }

        val expected = run(intArrayOf(1))
        for (chunks in listOf(intArrayOf(333), intArrayOf(960), intArrayOf(333, 297), intArrayOf(17, 333, 71, 960, 5, 241))) {
            assertArrayEquals(expected, run(chunks), 0f)
        }
    }

    @Test
    fun fullSnapshotResumesDuringHotEventAndShiftTail() {
        val a = N2Renderer(
            HybridTestProfiles.create(),
            N2Profile.preregistered(),
            N2Mode.SE,
            qualificationOnly = true,
            eventsAudible = true,
        )
        repeat(118) { n ->
            a.render(state(n * .02, n >= 100, shift = n == 110), 960)
        }
        val b = N2Renderer(
            HybridTestProfiles.create(),
            N2Profile.preregistered(),
            N2Mode.SE,
            qualificationOnly = true,
            eventsAudible = true,
        )
        b.restore(a.snapshot())
        repeat(30) { n ->
            val s = state(2.36 + n * .02, closed = true)
            assertArrayEquals(a.render(s, 960), b.render(s, 960), 0f)
        }
    }

    @Test
    fun malformedActualSoundStateCannotAdvanceRenderer() {
        val a = N2Renderer(
            HybridTestProfiles.create(),
            N2Profile.preregistered(),
            N2Mode.S,
            qualificationOnly = true,
        )
        val b = N2Renderer(
            HybridTestProfiles.create(),
            N2Profile.preregistered(),
            N2Mode.S,
            qualificationOnly = true,
        )
        assertThrows(IllegalArgumentException::class.java) {
            a.render(state(Double.NaN), 333)
        }
        assertArrayEquals(a.render(state(0.0), 333), b.render(state(0.0), 333), 0f)
    }
}
