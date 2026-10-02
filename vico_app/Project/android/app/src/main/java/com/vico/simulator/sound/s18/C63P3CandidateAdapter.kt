package com.vico.simulator.sound.s18

/**
 * Qualification-only P3 adapter.
 * It does not replace AudioEngine routing and cannot enable frozen HY1.
 */
internal data class C63CandidateArtifact(
    val candidateId: String,
    val profileHash: String,
    val sourceHash: String,
    val reportHash: String,
)

internal data class C63RuntimeCandidateReport(
    val artifact: C63CandidateArtifact,
    val eligible: Boolean,
    val reason: String,
)

internal class C63P3CandidateAdapter {
    private var active: C63CandidateArtifact? = null

    fun prepare(artifact: C63CandidateArtifact, qualification: QualificationResult): C63RuntimeCandidateReport {
        if (artifact.candidateId != qualification.candidateId) {
            return C63RuntimeCandidateReport(artifact, false, "candidate_identity_mismatch")
        }
        if (artifact.candidateId == "C63_HY1" || artifact.candidateId.startsWith("C63_HY1_")) {
            return C63RuntimeCandidateReport(artifact, false, "frozen_hy1_disabled")
        }
        if (!qualification.eligibleForRuntime) {
            return C63RuntimeCandidateReport(artifact, false, "qualification_incomplete")
        }
        active = artifact
        return C63RuntimeCandidateReport(artifact, true, "qualification_only_ready")
    }

    fun clear() { active = null }
    fun selectedArtifact(): C63CandidateArtifact? = active
}
