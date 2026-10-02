package com.vico.simulator.sound.n2.diagnostic

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.n2.*
import org.junit.Assert.*
import org.junit.Test

class N2QualificationTapBufferTest {
    private fun renderer() = N2Renderer(HybridTestProfiles.create(),
        N2ProfileArtifactLoader.import(N2ProfileArtifactLoader.export(N2Profile.calibrated()).bytes).profile, N2Mode.SE)
    private fun state() = SoundState(0.0, 5000.0, 0.0, .9, .9, floatArrayOf(), false, .9, .9)

    @Test fun preservesSevenStemsAndTwoImpulsesWithoutAliasingOrSilentOverflow() {
        val buffer = N2QualificationTapBuffer(1)
        val stems = DoubleArray(7) { it + .25 }
        buffer.append(stems, 42.0, 43.0)
        assertArrayEquals(doubleArrayOf(.25, 1.25, 2.25, 3.25, 4.25, 5.25, 6.25, 42.0, 43.0), buffer.copyFrames()[0], 0.0)
        stems.fill(0.0); buffer.copyFrames()[0].fill(0.0)
        assertEquals(5.25, buffer.copyFrames()[0][5], 0.0)
        assertThrows(IllegalArgumentException::class.java) { buffer.append(stems, 0.0, 0.0) }
        assertEquals(1, buffer.frameCount())
        buffer.reset(); assertEquals(0, buffer.frameCount())
        buffer.append(stems, 0.0, 0.0); assertEquals(1, buffer.frameCount())
    }

    @Test fun malformedAppendLeavesBufferUntouched() {
        val buffer = N2QualificationTapBuffer(2)
        assertThrows(IllegalArgumentException::class.java) { buffer.append(DoubleArray(6), 0.0, 0.0) }
        assertThrows(IllegalArgumentException::class.java) { buffer.append(DoubleArray(7), Double.NaN, 0.0) }
        assertThrows(IllegalArgumentException::class.java) { buffer.append(DoubleArray(7) { Double.POSITIVE_INFINITY }, 0.0, 0.0) }
        assertEquals(0, buffer.frameCount())
    }

    @Test fun overflowRejectsWholeRenderBeforeAnyStateOrBufferAdvances() {
        val actual = renderer(); val expected = renderer(); val tap = N2QualificationTapBuffer(1000)
        actual.render(state(), 960, tap = tap); expected.render(state(), 960)
        val before = tap.copyFrames()
        assertThrows(IllegalArgumentException::class.java) { actual.render(state(), 333, tap = tap) }
        assertEquals(960L, actual.frames); assertEquals(960, tap.frameCount())
        assertArrayEquals(before.last(), tap.copyFrames().last(), 0.0)
        assertArrayEquals(expected.render(state(), 333), actual.render(state(), 333), 0f)
    }

    @Test fun tapObservesActualSourceEveryFrameAndSnapshotReplayAndBufferReuseAreExact() {
        val a = renderer(); val b = renderer(); val tap = N2QualificationTapBuffer(960)
        repeat(333) { a.render(state(), 1, tap = tap) }
        assertArrayEquals(a.sourceStems(), tap.copyFrames().last().copyOfRange(0, 7), 0.0)
        b.restore(a.snapshot())
        tap.reset()
        val other = N2QualificationTapBuffer(960)
        val first = a.render(state(), 960, tap = tap).copyOf()
        assertArrayEquals(first, b.render(state(), 960, tap = other), 0f)
        assertArrayEquals(N2QualificationExport.tapBytes(tap.copyFrames()), N2QualificationExport.tapBytes(other.copyFrames()))
        val saved = tap.copyFrames()
        a.render(state(), 960)
        assertArrayEquals(N2QualificationExport.tapBytes(saved), N2QualificationExport.tapBytes(tap.copyFrames()))
    }
}
