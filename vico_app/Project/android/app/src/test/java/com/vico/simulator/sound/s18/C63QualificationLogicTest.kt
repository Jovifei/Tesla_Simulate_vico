package com.vico.simulator.sound.s18

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.HybridTestProfiles

class C63QualificationLogicTest {
    @Test
    fun emptyTrajectoryCannotProduceEvidence() {
        assertTrue(C63EventModeExport.compare(emptyList()) { error("No renderer needed") }.isEmpty())
    }

    @Test
    fun exportedPcmMatchesActualRendererAcrossAllModes() {
        val states = (0..2).map { n ->
            SoundState(n * .02, 700.0 + n * 1000, 0.0, .5, .5, floatArrayOf(), false, .5, .5)
        }
        for (mode in C63HybridMode.values()) {
            val profile = HybridTestProfiles.create()
            val results = C63EventModeExport.compare(states) { audible ->
                C63HybridRenderer(profile, mode, true, audible)
            }
            for ((index, audible) in listOf(true, false).withIndex()) {
                val renderer = C63HybridRenderer(profile, mode, true, audible)
                val expected = FloatArray(states.size * 960)
                states.forEachIndexed { i, state -> renderer.render(state, 960).copyInto(expected, i * 960) }
                val actual = results[index]
                assertArrayEquals(expected, actual.pcm, 0f)
                assertEquals(renderer.candidateId, actual.candidateId)
                assertEquals(expected.size, actual.frames)
                assertEquals(expected.maxOf { kotlin.math.abs(it.toDouble()) }, actual.peak, 0.0)
                assertTrue(actual.finite)
            }
        }
    }

    private fun passed(id: String): QualificationResult {
        val q = C63CandidateQualification(id)
        QualificationGate.values().forEach { q.markPassed(it) }
        return q.result()
    }

    @Test(expected = IllegalArgumentException::class)
    fun registryRejectsBorrowedQualification() {
        C63CandidateRegistry().register(C63CandidateRecord("new", passed("other")))
    }

    @Test
    fun registryRejectsFrozenHy1Variants() {
        val registry = C63CandidateRegistry()
        for (id in listOf("C63_HY1", "C63_HY1_SE_EVENT_OFF", "new")) {
            registry.register(C63CandidateRecord(id, passed(id)))
        }
        assertTrue(registry.runtimeCandidates().map { it.id } == listOf("new"))
    }

    @Test
    fun diagnosticsRetainFailureAfterHistoryEviction() {
        val diagnostics = C63QualificationDiagnostics(1)
        assertFalse(diagnostics.exportSummary()["finite"] as Boolean)
        diagnostics.record(C63DiagnosticFrame(0, 700.0, .1, .1, false, .8))
        diagnostics.record(C63DiagnosticFrame(1, 700.0, .1, .1, true, .2))
        val summary = diagnostics.exportSummary()
        assertFalse(summary["finite"] as Boolean)
        assertTrue(summary["max_peak"] == .8)
        assertTrue(summary["frames"] == 2L)
    }

    @Test
    fun emptyQualificationCannotEnableRuntime() {
        assertFalse(C63CandidateQualification("candidate").result().eligibleForRuntime)
    }

    @Test
    fun markNotRunRemovesPreviousPass() {
        val gate = C63CandidateQualification("candidate")
        gate.markPassed(QualificationGate.DIGITAL)
        gate.markNotRun(QualificationGate.DIGITAL, "repeat")
        assertFalse(gate.result().passed.contains(QualificationGate.DIGITAL))
        assertTrue(gate.result().notRun.contains(QualificationGate.DIGITAL))
    }

    @Test
    fun registryDoesNotEnableHy1() {
        val q = C63CandidateQualification("C63_HY1")
        QualificationGate.values().forEach { q.markPassed(it) }
        val record = C63CandidateRecord("C63_HY1", q.result())
        assertFalse(record.enabled)
    }
}
