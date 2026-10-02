package com.vico.simulator.sound

/**
 * Qualification-only PCM seam. This is intentionally not wired into the
 * production AudioEngine path yet. A caller must opt in explicitly and provide
 * a validated candidate. Legacy MatlabV6SoundBankEngine remains the default.
 */
internal interface C63QualificationPcmProvider {
    fun render(state: SoundState, frames: Int): FloatArray
    fun candidateId(): String
    fun qualification(): com.vico.simulator.sound.s18.C63QualificationReport? = null
    fun profileHash(): String? = null
    fun sourceHash(): String? = null
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

/** Default off; failed input/output clears the provider until explicitly prepared again. */
internal class C63QualificationRoute {
    @Volatile private var provider: C63QualificationPcmProvider? = null

    @Synchronized fun prepare(value: C63QualificationPcmProvider?): Boolean {
        clear()
        if (value == null) return false
        val valid = eligible(value)
        if (valid) provider = value
        return valid
    }

    private fun eligible(value: C63QualificationPcmProvider): Boolean = runCatching {
            val report = value.qualification() ?: return@runCatching false
            report.isRuntimeEligible() && report.candidateId == value.candidateId() &&
                report.profileHash == value.profileHash() && report.sourceHash == value.sourceHash()
    }.getOrDefault(false)

    @Synchronized fun clear() { provider = null }

    @Synchronized fun render(state: SoundState, frames: Int, sampleRate: Int): FloatArray? {
        val selected = provider ?: return null
        if (!eligible(selected) || sampleRate != 48000 || !validInput(state)) { clear(); return null }
        val output = runCatching { selected.render(state, frames) }.getOrNull()
        if (output == null || output.size != frames || output.any { !it.isFinite() || kotlin.math.abs(it) > 1f }) {
            clear(); return null
        }
        return output.copyOf()
    }

    companion object {
        fun validInput(state: SoundState): Boolean = state.timeS.isFinite() && state.rpm.isFinite() &&
            state.rpm >= 0 && state.load.isFinite() && state.load in 0.0..1.0 &&
            state.throttle.isFinite() && state.throttle in 0.0..1.0
    }
}
