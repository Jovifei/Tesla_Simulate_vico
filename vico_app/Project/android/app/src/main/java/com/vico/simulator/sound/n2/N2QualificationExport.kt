package com.vico.simulator.sound.n2

import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.s18.C63HybridProfile

internal data class N2RenderExport(
    val candidateId: String,
    val mode: N2Mode,
    val eventsAudible: Boolean,
    val sampleRate: Int,
    val channels: Int,
    val frames: Int,
    val measurement: N2Measurement.Result,
    val pcm: FloatArray,
)

/** Offline qualification export only. It cannot register or select N2 for runtime playback. */
internal object N2QualificationExport {
    fun renderAll(
        trajectory: List<SoundState>,
        baselineProfile: C63HybridProfile,
        profile: N2Profile = N2Profile.preregistered(),
    ): List<N2RenderExport> {
        if (trajectory.isEmpty()) return emptyList()
        val branches = listOf(
            N2Mode.T to true,
            N2Mode.S to true,
            N2Mode.E to true,
            N2Mode.E to false,
            N2Mode.SE to true,
            N2Mode.SE to false,
        )
        return branches.map { (mode, audible) ->
            render(trajectory, baselineProfile, profile, mode, audible)
        }
    }

    private fun render(
        trajectory: List<SoundState>,
        baselineProfile: C63HybridProfile,
        profile: N2Profile,
        mode: N2Mode,
        eventsAudible: Boolean,
    ): N2RenderExport {
        val renderer = N2Renderer(
            baselineProfile,
            profile,
            mode,
            qualificationOnly = true,
            eventsAudible = eventsAudible,
        )
        val pcm = FloatArray(trajectory.size * 960)
        trajectory.forEachIndexed { index, state ->
            renderer.render(state, 960).copyInto(pcm, index * 960)
        }
        val measurement = N2Measurement.measure(pcm)
        check(measurement.evidenceValid) { "N2 export produced invalid evidence" }
        return N2RenderExport(
            renderer.candidateId,
            mode,
            eventsAudible,
            N2Profile.SAMPLE_RATE,
            1,
            pcm.size,
            measurement,
            pcm,
        )
    }
}
