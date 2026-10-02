package com.vico.simulator.sound.s18

internal data class C63DiagnosticFrame(
    val frame: Long,
    val rpm: Double,
    val load: Double,
    val throttle: Double,
    val finite: Boolean,
    val peak: Double,
)

internal class C63QualificationDiagnostics {
    private val frames = mutableListOf<C63DiagnosticFrame>()

    fun record(frame: C63DiagnosticFrame) { frames += frame }

    fun exportSummary(): Map<String, Any> = mapOf(
        "frames" to frames.size,
        "finite" to frames.all { it.finite },
        "max_peak" to (frames.maxOfOrNull { it.peak } ?: 0.0),
        "candidate_routing" to "qualification_only",
    )
}
