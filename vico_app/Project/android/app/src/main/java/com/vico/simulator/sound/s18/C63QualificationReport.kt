package com.vico.simulator.sound.s18

internal data class C63QualificationReport(
    val candidateId: String,
    val profileHash: String,
    val sourceHash: String,
    val reportHash: String,
    val gates: Map<QualificationGate, Boolean>,
    val diagnostics: Map<String, Any>,
) {
    fun isRuntimeEligible(): Boolean =
        candidateId.isNotBlank() &&
            gates.values.size == QualificationGate.entries.size &&
            gates.values.all { it }
}
