package com.vico.simulator.sound.s18

/**
 * Offline-only qualification state. This never changes production routing.
 * Runtime enabling requires all declared gates to be explicitly passed.
 */
internal enum class QualificationGate { DIGITAL, STATE, CONTINUITY, ACOUSTIC, DEVICE, HUMAN }

internal data class QualificationResult(
    val candidateId: String,
    val passed: Set<QualificationGate>,
    val notRun: Set<QualificationGate>,
    val notes: List<String>
) {
    /**
     * Fail closed: runtime eligibility requires every engineering gate and
     * acoustic/device gates to be explicitly completed. Empty or unknown state
     * cannot become eligible.
     */
    val eligibleForRuntime: Boolean
        get() = notRun.isEmpty() && passed.containsAll(QualificationGate.entries.toSet())
}

internal class C63CandidateQualification(private val candidateId: String) {
    private val passed = linkedSetOf<QualificationGate>()
    private val notRun = linkedSetOf<QualificationGate>(*QualificationGate.entries.toTypedArray())
    private val notes = mutableListOf<String>()

    fun markPassed(gate: QualificationGate) {
        passed += gate
        notRun -= gate
    }

    fun markNotRun(gate: QualificationGate, reason: String) {
        passed -= gate
        notRun += gate
        notes += "$gate: $reason"
    }

    fun result(): QualificationResult = QualificationResult(
        candidateId,
        passed.toSet(),
        notRun.toSet(),
        notes.toList(),
    )
}
