package com.vico.simulator.sound.s18

/**
 * Offline-only qualification state. This never changes production routing.
 * Runtime enabling requires external approval after all gates pass.
 */
internal enum class QualificationGate { DIGITAL, STATE, CONTINUITY, ACOUSTIC, DEVICE, HUMAN }

internal data class QualificationResult(
    val candidateId: String,
    val passed: Set<QualificationGate>,
    val notRun: Set<QualificationGate>,
    val notes: List<String>
) {
    val eligibleForRuntime: Boolean
        get() = passed.containsAll(setOf(QualificationGate.DIGITAL, QualificationGate.STATE, QualificationGate.CONTINUITY))
            && !notRun.contains(QualificationGate.DIGITAL)
}

internal class C63CandidateQualification(private val candidateId: String) {
    private val passed = linkedSetOf<QualificationGate>()
    private val notRun = linkedSetOf<QualificationGate>(
        QualificationGate.ACOUSTIC,
        QualificationGate.DEVICE,
        QualificationGate.HUMAN,
    )
    private val notes = mutableListOf<String>()

    fun markPassed(gate: QualificationGate) { passed += gate; notRun -= gate }
    fun markNotRun(gate: QualificationGate, reason: String) { notRun += gate; notes += "$gate: $reason" }
    fun result() = QualificationResult(candidateId, passed.toSet(), notRun.toSet(), notes.toList())
}
