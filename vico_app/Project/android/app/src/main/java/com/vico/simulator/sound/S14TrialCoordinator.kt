package com.vico.simulator.sound

/** UI-thread owner for asynchronous loading, completion and export. */
class S14TrialCoordinator {
    enum class State { IDLE, LOADING, READY, PLAYING, DRAINING, EXPORTING, FINISHED, ABORTED, FAILED }
    data class Ticket(val id: String, val label: String, val controlled: Boolean = false)
    private var sequence = 0L
    var ticket: Ticket? = null
        private set
    var state = State.IDLE
        private set
    var error: String? = null
        private set
    val busy get() = state in setOf(State.LOADING, State.READY, State.PLAYING, State.DRAINING, State.EXPORTING)

    fun begin(label: String, controlled: Boolean = false): Ticket {
        check(!busy)
        require(label in setOf("R", "M"))
        return Ticket("${System.nanoTime()}-${++sequence}", label, controlled).also {
            ticket = it; state = State.LOADING; error = null
        }
    }
    fun owns(owner: Ticket) = ticket == owner
    fun advance(owner: Ticket, next: State): Boolean {
        if (!owns(owner)) return false
        val allowed = when (state) {
            State.LOADING -> setOf(State.READY, State.ABORTED, State.FAILED)
            State.READY -> setOf(State.PLAYING, State.ABORTED, State.FAILED)
            State.PLAYING -> setOf(State.DRAINING, State.EXPORTING, State.ABORTED, State.FAILED)
            State.DRAINING -> setOf(State.EXPORTING, State.ABORTED, State.FAILED)
            State.EXPORTING -> setOf(State.FINISHED, State.ABORTED, State.FAILED)
            else -> emptySet()
        }
        if (next !in allowed) return false
        state = next
        return true
    }
    fun fail(owner: Ticket, reason: String) {
        if (owns(owner) && busy) { error = reason; state = State.FAILED }
    }
    fun abort(owner: Ticket, reason: String) { if (advance(owner, State.ABORTED)) error = reason }
}

/** Tokens are invalidated on Stop, a new playback, and Activity destruction. */
class S14CallbackEpoch {
    private var generation = 0L
    fun next(): Long = ++generation
    fun owns(token: Long) = generation == token
}

data class S14OutputConditions(
    val deviceInstance: String, val model: String, val sdk: Int, val routeId: Int, val routeType: Int,
    val routeCategory: String, val routeName: String, val mediaVolume: Int,
    val mediaVolumeMax: Int, val mediaMuted: Boolean,
)

data class S14PlaybackResult(
    val ticket: S14TrialCoordinator.Ticket, val sourceSha: String,
    val startedAtMs: Long, val endedAtMs: Long,
    val startConditions: S14OutputConditions?, val endConditions: S14OutputConditions?,
    val renderedFrames: Int, val playbackHeadFrames: Long?, val playbackPositionComplete: Boolean?,
    val submittedComplete: Boolean, val error: String?,
)

class S14CompletedCapture internal constructor(
    val result: S14PlaybackResult,
    private val core: BoundedPcmCapture,
    private val accepted: BoundedPcmCapture,
) {
    fun exportCore(output: java.io.OutputStream) = core.exportF32le(output)
    fun exportAccepted(output: java.io.OutputStream) = accepted.exportF32le(output)
}
