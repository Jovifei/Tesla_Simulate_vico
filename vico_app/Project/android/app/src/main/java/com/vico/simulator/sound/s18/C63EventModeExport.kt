package com.vico.simulator.sound.s18

import com.vico.simulator.sound.SoundState
import kotlin.math.abs

internal data class C63RenderComparison(
    val candidateId: String,
    val eventsAudible: Boolean,
    val sampleRate: Int,
    val channels: Int,
    val frames: Int,
    val finite: Boolean,
    val peak: Double,
    val pcm: FloatArray,
)

/** Offline comparison only. Never selects a production renderer. */
internal object C63EventModeExport {
    fun compare(
        trajectory: List<SoundState>,
        rendererFactory: (eventsAudible: Boolean) -> C63HybridRenderer,
    ): List<C63RenderComparison> {
        if (trajectory.isEmpty()) return emptyList()
        return listOf(
            render(trajectory, true, rendererFactory(true)),
            render(trajectory, false, rendererFactory(false)),
        )
    }

    private fun render(
        trajectory: List<SoundState>,
        eventsAudible: Boolean,
        renderer: C63HybridRenderer,
    ): C63RenderComparison {
        val pcm = ArrayList<Float>(trajectory.size * 960)
        var finite = true
        var peak = 0.0
        trajectory.forEach { state ->
            val block = renderer.render(state, 960).copyOf()
            block.forEach { sample ->
                val value = sample.toDouble()
                finite = finite && value.isFinite()
                peak = maxOf(peak, abs(value))
            }
            pcm.addAll(block.asList())
        }
        return C63RenderComparison(
            candidateId = renderer.candidateId,
            eventsAudible = eventsAudible,
            sampleRate = 48000,
            channels = 1,
            frames = pcm.size,
            finite = finite,
            peak = peak,
            pcm = pcm.toFloatArray(),
        )
    }
}
