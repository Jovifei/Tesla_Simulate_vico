package com.vico.simulator.sound

/** Synthetic QA frames only; gear is an opaque integer until its contract is established. */
data class V14SyntheticFrame(val throttle: Double, val rpm: Double, val load: Double, val gear: Int)

internal class V14SyntheticController(private val publish: (SoundState?) -> Unit) {
    private var generation = 0L
    private var lastSequence = -1L
    private var lastTimeS = -1.0
    private var lastNowNanos = -1L
    private var active = false

    @Synchronized fun begin(): Long {
        generation++
        active = true
        lastSequence = -1L
        lastTimeS = -1.0
        lastNowNanos = -1L
        publish(null)
        return generation
    }

    @Synchronized fun submit(owner: Long, sequence: Long, nowNanos: Long, validUntilNanos: Long,
                             timeS: Double, frame: V14SyntheticFrame): Boolean {
        if (!active || owner != generation) return false
        if (sequence <= lastSequence || nowNanos < 0 || nowNanos < lastNowNanos || validUntilNanos <= nowNanos ||
            validUntilNanos - nowNanos > 2_000_000_000L || !timeS.isFinite() || timeS < 0 ||
            timeS < lastTimeS ||
            !frame.throttle.isFinite() || frame.throttle !in 0.0..1.0 ||
            !frame.rpm.isFinite() || frame.rpm < 0 || !frame.load.isFinite() || frame.load !in 0.0..1.0) {
            active = false
            publish(null)
            return false
        }
        lastSequence = sequence
        lastTimeS = timeS
        lastNowNanos = nowNanos
        publish(SoundState(timeS, frame.rpm, 0.0, frame.load, frame.load, floatArrayOf(), false,
            throttle = frame.throttle, load = frame.load, gear = frame.gear,
            inputControl = DriveInputControl(DriveInputSource.SYNTHETIC_AUDITION, owner,
                validUntilNanos, true, true, controlFrameId = sequence, controlTimeElapsedNanos = nowNanos)))
        return true
    }

    @Synchronized fun stop(owner: Long) {
        if (active && owner == generation) { active = false; publish(null) }
    }

    @Synchronized fun cancel() {
        if (active) { active = false; generation++; publish(null) }
    }
}
