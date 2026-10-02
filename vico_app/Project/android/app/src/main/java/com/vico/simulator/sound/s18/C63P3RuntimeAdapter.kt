package com.vico.simulator.sound.s18

/**
 * P3 runtime boundary. This adapter is intentionally not wired into AudioEngine.
 * Production continues using the existing Matlab sound bank until qualification passes.
 */
internal class C63P3RuntimeAdapter(
    private val registry: C63CandidateRegistry,
) {
    data class Decision(
        val enabled: Boolean,
        val reason: String,
    )

    fun select(candidateId: String?): Decision {
        if (candidateId == null) return Decision(false, "no_candidate")
        val record = registry.find(candidateId)
            ?: return Decision(false, "candidate_missing")
        if (!record.enabled) return Decision(false, "qualification_failed")
        return Decision(true, "qualification_passed")
    }

    fun fallbackDecision(): Decision = Decision(false, "fallback_legacy_sound_bank")
}
