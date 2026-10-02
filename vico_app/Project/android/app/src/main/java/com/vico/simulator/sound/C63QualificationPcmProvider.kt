package com.vico.simulator.sound

/**
 * Qualification-only PCM seam. This is intentionally not wired into the
 * production AudioEngine path yet. A caller must opt in explicitly and provide
 * a validated candidate. Legacy MatlabV6SoundBankEngine remains the default.
 */
internal interface C63QualificationPcmProvider {
    fun render(state: SoundState, frames: Int): FloatArray
    fun candidateId(): String
}

internal class C63QualificationSelector {
    fun select(
        provider: C63QualificationPcmProvider?,
        candidateId: String?,
        eligible: Boolean,
        inputValid: Boolean,
    ): C63QualificationPcmProvider? {
        if (!eligible || !inputValid || provider == null) return null
        if (candidateId == null || provider.candidateId() != candidateId) return null
        if (candidateId == "C63_HY1" || candidateId.startsWith("C63_HY1_")) return null
        return provider
    }
}
