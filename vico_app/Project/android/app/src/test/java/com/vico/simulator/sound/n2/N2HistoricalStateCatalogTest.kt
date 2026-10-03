package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.n2.diagnostic.N2QualificationTapBuffer
import com.vico.simulator.sound.s18.C63HybridProfile
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class N2HistoricalStateCatalogTest {
    companion object {
        private val catalog by lazy { N2HistoricalStateCatalog.fromCheckedInTrace() }
        private val baseline get() = HybridTestProfiles.create().toBytes()
        private val artifact get() = N2ProfileArtifactLoader.export(N2Profile.calibrated()).bytes
    }

    @Test fun historicalInventoryHasExactCountsAndNeverInventsMissingStates() {
        assertEquals(mapOf("Q0" to 49, "Q1" to 2, "Q2" to 76, "Q3" to 6, "Q4" to 200,
            "H1" to 290, "H2" to 6, "H3" to 1), catalog.entries.groupingBy { it.group }.eachCount())
        assertEquals(630, catalog.entries.size)
        assertEquals(338, catalog.available.size)
        assertEquals(74_697_600L, catalog.totalAvailableFrames)
        val missing = catalog.entries.filterNot { it.available }
        assertEquals(292, missing.size)
        assertEquals(setOf("Q0_phone", "Q1_phone_plus_hold") + (0..289).map { "H1_$it" }, missing.map { it.id }.toSet())
        missing.forEach {
            assertNull(it.frames); assertNull(it.segments); assertNull(it.fixtureSha256); assertNull(it.historicalInputSha256)
            assertThrows(IllegalStateException::class.java) { it.fixture() }
        }
        assertEquals("32ca93bb3284f95bc4a6a383d5bd12053fd7d95eeb02cfd5a12451f985b0b60a", catalog.sha256)
    }

    @Test fun historicalDurationsAndFloatingPointControlSemanticsStayExact() {
        assertEquals(1500, catalog.entry("Q1_original").segments)
        val original = catalog.entry("Q1_original").fixture().segments()
        assertEquals(listOf(306, 432, 558), original.indices.filter { original[it].state.shiftTrigger })
        assertEquals(29.98, original.last().state.timeS, 0.0)
        assertEquals(3_120_000, catalog.entry("Q3_sweep_true").frames)
        assertEquals(3_120_000, catalog.entry("H2_12.0_false").frames)
        assertEquals(3_216_000, catalog.entry("H2_12.0_true").frames)
        val hot = catalog.entry("Q4_1849.0_0.32_0.35_true").fixture().segments()
        assertEquals(-2.0, hot.first().state.timeS, 0.0)
        assertEquals(0.0, hot[100].state.timeS, 0.0)
        assertEquals(.32, hot[100].state.amplitude, 0.0)
        assertEquals(.32, hot[100].state.brightness, 0.0)
        assertEquals(1849.0 / 60 * 4, hot[100].state.frequencyHz, 0.0)
        val h2 = catalog.entry("H2_0.12_true").fixture().segments()
        var time = 0.0; repeat(100) { time += .02 }
        assertEquals(time, h2[100].state.timeS, 0.0)
        assertNotEquals(2.0, time)
        assertTrue(catalog.available.all { entry -> entry.fixture().segments().all { it.frames == 960 && it.validInput } })
    }

    @Test fun catalogAndFixtureIdentitiesAreImmutableAndSourceBound() {
        val original = catalog.bytes()
        assertEquals(catalog.sha256, N2QualificationExport.sha(original))
        catalog.bytes().fill(0)
        assertArrayEquals(original, catalog.bytes())
        assertThrows(UnsupportedOperationException::class.java) { (catalog.entries as MutableList).clear() }
        assertThrows(UnsupportedOperationException::class.java) { (catalog.available as MutableList).clear() }
        val entry = catalog.entry("Q1_original")
        val before = entry.fixture().bytes()
        entry.fixture().bytes().fill(0)
        assertArrayEquals(before, entry.fixture().bytes())
        val trace = N2HistoricalStateCatalog.checkedInTraceFile().canonicalFile
        val app = trace.parentFile.parentFile.parentFile.parentFile.parentFile.parentFile
        assertEquals(trace, N2HistoricalStateCatalog.checkedInTraceFile(app).canonicalFile)
        assertEquals(trace, N2HistoricalStateCatalog.checkedInTraceFile(app.parentFile).canonicalFile)
        assertThrows(IllegalArgumentException::class.java) { N2HistoricalStateCatalog.checkedInTraceFile(trace.parentFile) }
        val corrupt = trace.readBytes().also { it[0] = 0 }
        assertThrows(IllegalArgumentException::class.java) { N2HistoricalStateCatalog(corrupt) }
    }

    @Test fun completeRepresentativeCasesStreamSixActualBranchesWithoutNormalizing() {
        val verifier = N2HistoricalDigitalVerification(baseline, artifact)
        for (id in listOf("Q0_steady_700.0_0.0", "Q4_1849.0_0.32_0.35_true", "H3_events")) {
            val fixture = catalog.entry(id).fixture()
            N2QualificationExport.branches.forEach { (mode, audible) ->
                val a = verifier.render(fixture, mode, audible)
                val b = verifier.render(fixture, mode, audible, intArrayOf(333, 297))
                assertEquals(a, b)
                assertEquals(fixture.frames.toLong(), a.frames)
                assertTrue("$id/$mode/$audible peak=${a.peak}", a.digitalPass)
                assertTrue(a.energy.isFinite() && a.energy > 0 && a.rms > 0)
                assertEquals(9, a.tapEnergies.size)
                assertTrue(a.tapEnergies.all { it.isFinite() && it >= 0 })
            }
        }
    }

    @Test fun streamedBytesEqualExistingExporterAndRejectInvalidInputs() {
        val verifier = N2HistoricalDigitalVerification(baseline, artifact)
        val segments = catalog.entry("H3_events").fixture().segments().take(3)
        val small = N2QualificationFixture("stream-cross-check", segments)
        N2QualificationExport.renderAll(small, baseline, artifact).forEach { expected ->
            val actual = verifier.render(small, expected.mode, expected.eventsAudible)
            assertEquals(N2QualificationExport.sha(N2QualificationExport.pcmBytes(expected.pcm)), actual.pcmSha256)
            assertEquals(N2QualificationExport.sha(N2QualificationExport.tapBytes(expected.sourceTaps)), actual.tapSha256)
            assertEquals(expected.measurement.peak, actual.peak, 0.0)
            assertEquals(expected.measurement.rms, actual.rms, 0.0)
        }
        listOf(intArrayOf(), intArrayOf(0), intArrayOf(4801)).forEach {
            assertThrows(IllegalArgumentException::class.java) { verifier.render(small, N2Mode.SE, true, it) }
        }
        assertThrows(IllegalArgumentException::class.java) { N2HistoricalDigitalVerification(ByteArray(4), artifact) }
        assertThrows(IllegalArgumentException::class.java) { N2HistoricalDigitalVerification(baseline, ByteArray(4)) }
    }

    @Test fun frozenTEquivalenceIsSeparatelyCheckedOnHistoricalTransitionAndEvents() {
        val verifier = N2HistoricalDigitalVerification(baseline, artifact)
        for (id in listOf("Q0_transition_7200.0_700.0", "H3_events")) {
            val fixture = catalog.entry(id).fixture()
            assertEquals(fixture.frames.toLong(), verifier.verifyFrozenT(fixture, intArrayOf(17, 333, 71, 960, 5, 241)))
        }
    }

    @Test fun snapshotReplayIsSeparatelyCheckedInsideHistoricalHotShiftAndEventTail() {
        val segments = catalog.entry("H3_events").fixture().segments()
        val base = C63HybridProfile.fromBytes(baseline)
        val profile = N2ProfileArtifactLoader.import(artifact).profile
        N2QualificationExport.branches.forEach { (mode, audible) ->
            val a = N2Renderer(base, profile, mode, true, audible)
            segments.take(250).forEach { a.render(it.state, it.frames, it.validInput) }
            a.render(segments[250].state, 333)
            val b = N2Renderer(base, profile, mode, true, audible)
            b.restore(a.snapshot())
            val tapA = N2QualificationTapBuffer(960); val tapB = N2QualificationTapBuffer(960)
            val replay = listOf(segments[250].copy(frames = 627)) + segments.drop(251).take(30)
            replay.forEach { s ->
                tapA.reset(); tapB.reset()
                assertArrayEquals(a.render(s.state, s.frames, s.validInput, tapA), b.render(s.state, s.frames, s.validInput, tapB), 0f)
                assertArrayEquals(N2QualificationExport.tapBytes(tapA.copyFrames()), N2QualificationExport.tapBytes(tapB.copyFrames()))
            }
            assertEquals(a.frames, b.frames)
            assertEquals(a.peak, b.peak, 0.0)
            assertEquals(a.pendingFrames, b.pendingFrames)
            assertArrayEquals(a.eventObservation().arrivalFrames, b.eventObservation().arrivalFrames)
        }
    }
}
