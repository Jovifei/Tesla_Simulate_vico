package com.vico.simulator.sensor

/** UI-thread owned lifecycle; the immutable snapshot is safe for the WebView bridge reader. */
class CalibrationSession {
    enum class Status { IDLE, SAMPLING, COMPLETE, FAILED, CANCELLED }
    data class Snapshot(
        val session: String = "",
        val status: Status = Status.IDLE,
        val samples: Int = 0,
        val required: Int = 24,
        val revision: Long = 0,
    )

    private val accumulator = CalibrationAccumulator()
    private var startedNanos = 0L
    @Volatile var snapshot = Snapshot()
        private set
    val isCalibrated: Boolean get() = snapshot.status == Status.COMPLETE

    fun begin(session: String, nowNanos: Long, available: Boolean = true) {
        if (session.isBlank() || session == snapshot.session) return
        accumulator.reset()
        startedNanos = nowNanos
        snapshot = Snapshot(session, if (available) Status.SAMPLING else Status.FAILED,
            revision = snapshot.revision + 1)
    }

    fun add(sample: FloatArray, timestampNanos: Long) {
        if (snapshot.status != Status.SAMPLING || timestampNanos < startedNanos ||
            sample.size < 3 || (0..2).any { !sample[it].isFinite() } || accumulator.isReady) return
        accumulator.add(sample)
        val invalidBias = accumulator.isReady && accumulator.offsets().any { !it.isFinite() }
        if (invalidBias) accumulator.reset()
        snapshot = snapshot.copy(samples = snapshot.samples + 1,
            status = if (invalidBias) Status.FAILED else Status.SAMPLING,
            revision = snapshot.revision + 1)
    }

    fun finish(session: String): Boolean {
        if (session != snapshot.session || snapshot.status != Status.SAMPLING) return false
        val ready = accumulator.isReady && accumulator.offsets().all { it.isFinite() }
        if (!ready) accumulator.reset()
        snapshot = snapshot.copy(status = if (ready) Status.COMPLETE else Status.FAILED,
            revision = snapshot.revision + 1)
        return ready
    }

    fun cancel(session: String? = null) {
        if (snapshot.status != Status.SAMPLING || (session != null && session != snapshot.session)) return
        accumulator.reset()
        snapshot = snapshot.copy(status = Status.CANCELLED, samples = 0, revision = snapshot.revision + 1)
    }

    fun reset() {
        accumulator.reset()
        snapshot = Snapshot(revision = snapshot.revision + 1)
    }

    fun offsets(): FloatArray = accumulator.offsets()

    fun correct(sample: FloatArray): FloatArray = accumulator.correct(sample)
}
