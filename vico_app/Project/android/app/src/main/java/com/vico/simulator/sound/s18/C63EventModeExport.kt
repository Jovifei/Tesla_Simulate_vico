package com.vico.simulator.sound.s18

internal data class C63RenderComparison(
    val candidateId: String,
    val eventsAudible: Boolean,
    val sampleRate: Int = 48000,
    val channels: Int = 1,
    val frames: Int,
    val finite: Boolean,
)

internal class C63EventModeExport {
    fun compare(candidateId: String, frames: Int, finite: Boolean): List<C63RenderComparison> = listOf(
        C63RenderComparison(candidateId, true, frames = frames, finite = finite),
        C63RenderComparison(candidateId + "_EVENT_OFF", false, frames = frames, finite = finite),
    )
}
