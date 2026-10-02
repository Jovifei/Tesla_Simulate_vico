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
)

/** Offline comparison only. Never selects a production renderer. */
internal object C63EventModeExport {
    fun compare(
        trajectory: List<SoundState>,
        rendererFactory: (eventsAudible: Boolean) -> C63HybridRenderer,
    ): List<C63RenderComparison> = listOf(
        render(trajectory, true, rendererFactory(true)),
        render(trajectory, false, rendererFactory(false)),
    )

    private fun render(
        trajectory: List<SoundState>,
        eventsAudible: Boolean,
        renderer: C63HybridRenderer,
    ): C63RenderComparison {
        var frames = 0
        var finite = true
        var peak = 0.0
        trajectory.forEach { state ->
            renderer.render(state, 960).forEach { sample ->
                val value = sample.toDouble()
                frames++
                finite = finite && value.isFinite()
                peak = maxOf(peak, abs(value))
            }
        }
        return C63RenderComparison(
            candidateId = renderer.snapshot().candidateId,
            eventsAudible = eventsAudible,
            sampleRate = 48000,
            channels = 1,
            frames = frames,
            finite = finite,
            peak = peak,
        )
    }
}
