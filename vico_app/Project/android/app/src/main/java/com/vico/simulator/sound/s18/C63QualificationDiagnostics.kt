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
    private var count = 0L
    private var allFinite = true
    private var maxPeak = 0.0

    init { require(capacity > 0) }

    fun record(frame: C63DiagnosticFrame) {
        count++
        allFinite = allFinite && frame.finite && frame.peak.isFinite()
        maxPeak = maxOf(maxPeak, frame.peak)
        if (frames.size == capacity) frames.removeFirst()
        frames.addLast(frame)
    }

    fun exportSummary(): Map<String, Any> {
        if (count == 0L) {
            return mapOf(
                "status" to "NOT_RUN",
                "frames" to 0,
                "finite" to false,
                "max_peak" to 0.0,
                "candidate_routing" to "qualification_only",
            )
        }
        return mapOf(
            "status" to "RECORDED",
            "frames" to count,
            "finite" to allFinite,
            "max_peak" to maxPeak,
            "retained_frames" to frames.size,
            "candidate_routing" to "qualification_only",
        )
    }
}
