package com.vico.simulator.sound.s18

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class C63QualificationLogicTest {
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
