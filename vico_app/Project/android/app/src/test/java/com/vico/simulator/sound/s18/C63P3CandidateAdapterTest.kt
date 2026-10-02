package com.vico.simulator.sound.s18

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class C63P3CandidateAdapterTest {
    @Test
    fun rejectedPreparationClearsPreviousArtifact() {
        val adapter = C63P3CandidateAdapter()
        val hash = "a".repeat(64)
        val artifact = C63CandidateArtifact("candidate", hash, hash, hash)
        val qualification = QualificationResult("candidate", QualificationGate.entries.toSet(), emptySet(), emptyList())
        assertTrue(adapter.prepare(artifact, qualification).eligible)
        assertFalse(adapter.prepare(artifact.copy(profileHash = "unknown"), qualification).eligible)
        assertTrue(adapter.selectedArtifact() == null)
    }

    @Test
    fun identityMismatchCannotPrepareRuntimeCandidate() {
        val adapter = C63P3CandidateAdapter()
        val artifact = C63CandidateArtifact("candidate-a", "p", "s", "r")
        val result = adapter.prepare(artifact, QualificationResult("candidate-b", emptySet(), emptySet(), emptyList()))
        assertFalse(result.eligible)
    }

    @Test
    fun frozenHy1CannotPrepareRuntimeCandidate() {
        val adapter = C63P3CandidateAdapter()
        val artifact = C63CandidateArtifact("C63_HY1_SE", "p", "s", "r")
        val gates = QualificationGate.entries.toSet()
        val result = adapter.prepare(artifact, QualificationResult("C63_HY1_SE", gates, emptySet(), emptyList()))
        assertFalse(result.eligible)
    }

    @Test
    fun incompleteQualificationDoesNotSelectCandidate() {
        val adapter = C63P3CandidateAdapter()
        val artifact = C63CandidateArtifact("candidate-new", "p", "s", "r")
        val result = adapter.prepare(artifact, QualificationResult("candidate-new", emptySet(), QualificationGate.entries.toSet(), emptyList()))
        assertFalse(result.eligible)
        assertTrue(adapter.selectedArtifact() == null)
    }
}
