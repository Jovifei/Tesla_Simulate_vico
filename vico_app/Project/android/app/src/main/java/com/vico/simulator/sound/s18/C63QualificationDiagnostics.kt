package com.vico.simulator.sound.s18

internal data class C63DiagnosticFrame(
    val frame: Long,
    val rpm: Double,
    val load: Double,
    val throttle: Double,
    val finite: Boolean,
    val peak: Double,
)

internal class C63QualificationDiagnostics(private val capacity: Int = 4096) {
    private val frames = ArrayDeque<C63DiagnosticFrame>()

    fun record(frame: C63DiagnosticFrame) {
        if (frames.size == capacity) frames.removeFirst()
        frames.addLast(frame)
    }

    fun exportSummary(): Map<String, Any> {
        if (frames.isEmpty()) {
            return mapOf(
                "status" to "NOT_RUN",
                "frames" to 0,
                "finite" to false,
                "candidate_routing" to "qualification_only",
            )
        }
        return mapOf(
            "status" to "RECORDED",
            "frames" to frames.size,
            "finite" to frames.all { it.finite && it.peak.isFinite() },
            "max_peak" to (frames.maxOfOrNull { it.peak } ?: 0.0),
            "candidate_routing" to "qualification_only",
        )
    }
}
