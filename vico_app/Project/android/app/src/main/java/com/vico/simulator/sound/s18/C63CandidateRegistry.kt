package com.vico.simulator.sound.s18

/**
 * Offline candidate registry only. It does not alter AudioEngine routing.
 */
internal data class C63CandidateRecord(
    val id: String,
    val qualification: QualificationResult,
) {
    val enabled: Boolean get() = qualification.eligibleForRuntime && id != "C63_HY1"
}

internal class C63CandidateRegistry {
    private val records = linkedMapOf<String, C63CandidateRecord>()

    fun register(record: C63CandidateRecord) {
        require(record.id.isNotBlank())
        records[record.id] = record
    }

    fun find(id: String): C63CandidateRecord? = records[id]

    fun runtimeCandidates(): List<C63CandidateRecord> = records.values.filter { it.enabled }
}
