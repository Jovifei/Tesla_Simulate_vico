package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import org.junit.Assert.*
import org.junit.Test

class N2QualificationExportTest {
    private fun state(n: Int) = SoundState(n * .02, 3500.0 + n * 100.0, 0.0, .6, .7,
        floatArrayOf(.1f, .2f), false, .6, .7, shiftTrigger = n == 1)
    private val baseline get() = HybridTestProfiles.create().toBytes()
    private val artifact get() = N2ProfileArtifactLoader.export(N2Profile.calibrated()).bytes
    private fun fixture() = N2QualificationFixture("short-trajectory-v1", (0..2).map {
        N2TrajectorySegment(state(it), 960)
    })

    @Test fun emptyTrajectoryProducesNoEvidence() {
        assertThrows(IllegalArgumentException::class.java) { N2QualificationFixture("empty", emptyList()) }
    }

    @Test fun sixBranchesUseImportedProfileAndPreserveEveryFrameAcrossRealPartitions() {
        val bytes = artifact
        val f = fixture()
        val expected = N2QualificationExport.renderAll(f, baseline, bytes)
        val actual = N2QualificationExport.renderAll(f, baseline, bytes, intArrayOf(333, 297))
        assertEquals(N2QualificationExport.branches, actual.map { it.mode to it.eventsAudible })
        expected.zip(actual).forEach { (a, b) ->
            assertEquals(2880, b.frames); assertEquals(48000, b.sampleRate); assertEquals(1, b.channels)
            assertEquals(N2QualificationExport.sha(bytes), b.artifactSha256)
            assertEquals(N2ProfileArtifactLoader.import(bytes).profile.identity, b.profileIdentity)
            assertEquals(f.sha256, b.fixtureSha256)
            assertEquals(N2QualificationExport.sha(baseline), b.baselineArtifactSha256)
            assertTrue(b.measurement.evidenceValid)
            assertArrayEquals(a.pcm, b.pcm, 0f)
            assertArrayEquals(N2QualificationExport.tapBytes(a.sourceTaps), N2QualificationExport.tapBytes(b.sourceTaps))
            assertEquals(b.frames, b.sourceTaps.size)
            assertTrue(b.sourceTaps.all { it.size == 9 && it.all(Double::isFinite) })
            assertTrue(b.sourceTaps.any { it[5] != 0.0 })
            assertTrue(b.sourceTaps.any { it[6] != 0.0 })
        }
    }

    @Test fun exactFixtureIdentityIncludesControlsDurationAndUnusedInputFields() {
        val state = state(0)
        fun f(s: SoundState = state, count: Int = 960, valid: Boolean = true) =
            N2QualificationFixture("identity", listOf(N2TrajectorySegment(s, count, valid)))
        val original = f()
        assertNotEquals(original.sha256, f(count = 961).sha256)
        assertNotEquals(original.sha256, f(valid = false).sha256)
        assertNotEquals(original.sha256, f(state.copy(shiftTrigger = true)).sha256)
        assertNotEquals(original.sha256, f(state.copy(brightness = .8)).sha256)
        state.harmonics[0] = .8f
        assertNotEquals(original.sha256, f().sha256)
        original.segments()[0].state.harmonics[0] = .9f
        original.bytes().fill(0)
        assertEquals(original.sha256, N2QualificationExport.sha(original.bytes()))
        assertEquals(.1f, original.segments()[0].state.harmonics[0])
    }

    @Test fun malformedArtifactsAndPartitionsCannotProduceEvidence() {
        for (parts in listOf(intArrayOf(), intArrayOf(0), intArrayOf(4801))) {
            assertThrows(IllegalArgumentException::class.java) {
                N2QualificationExport.renderAll(fixture(), baseline, artifact, parts)
            }
        }
        val bad = artifact.also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }
        assertThrows(IllegalArgumentException::class.java) {
            N2QualificationExport.renderAll(fixture(), baseline, bad)
        }
        assertThrows(IllegalArgumentException::class.java) {
            N2QualificationExport.renderAll(fixture(), ByteArray(4), artifact)
        }
    }
}
