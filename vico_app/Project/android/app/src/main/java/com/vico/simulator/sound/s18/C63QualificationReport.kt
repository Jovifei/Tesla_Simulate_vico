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
            candidateId != "C63_HY1" && !candidateId.startsWith("C63_HY1_") &&
            listOf(profileHash, sourceHash, reportHash).all { it.matches(Regex("[0-9a-f]{64}")) } &&
            diagnostics["finite"] == true &&
            (diagnostics["frames"] as? Number)?.toLong()?.let { it > 0 } == true &&
            gates.values.size == QualificationGate.entries.size &&
            gates.values.all { it }
}
