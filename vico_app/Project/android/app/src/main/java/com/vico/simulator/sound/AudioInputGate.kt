package com.vico.simulator.sound

/** Audio-writer owned; observes expiry even when the control/UI thread stops publishing. */
class AudioInputGate {
    data class Decision(val usable: Boolean, val clearTransients: Boolean, val allowEvents: Boolean)
    private var initialized = false
    private var previousSource: DriveInputSource? = null
    private var previousEpoch: Long? = null
    private var previousModelRevision: Long? = null
    private var previousUsable = false
    private var previouslyRunning = true
    private var suppressedRealTimeS = Double.NaN

    fun evaluate(control: DriveInputControl?, stateTimeS: Double, nowElapsedNanos: Long, running: Boolean = true): Decision {
        val source = control?.source
        val usable = stateTimeS.isFinite() && when (source) {
            DriveInputSource.REAL -> control.usable && control.modelContinuityRevision >= 0L && control.validUntilElapsedNanos > 0L &&
                nowElapsedNanos >= 0L && nowElapsedNanos <= control.validUntilElapsedNanos
            DriveInputSource.DEMO, DriveInputSource.PREVIEW, DriveInputSource.QUALIFICATION -> control.usable
            DriveInputSource.UNSPECIFIED, null -> false
        }
        val identityChanged = previousSource != source || previousEpoch != control?.epoch ||
            previousModelRevision != control?.modelContinuityRevision
        val transition = !initialized || identityChanged || previousUsable != usable || previouslyRunning && !running
        if (transition && source == DriveInputSource.REAL) suppressedRealTimeS = stateTimeS
        initialized = true
        previousSource = source
        previousEpoch = control?.epoch
        previousModelRevision = control?.modelContinuityRevision
        previousUsable = usable
        previouslyRunning = running
        // Suppress the complete first resumed snapshot, including repeated audio reads of it.
        val allowEvents = usable && running && (source != DriveInputSource.REAL || stateTimeS != suppressedRealTimeS)
        return Decision(usable, transition, allowEvents)
    }
}

/** Experimental renderer has no event-only reset; require a fresh explicit preparation after rejection. */
class PrototypeInputGuard {
    private var rejected = false
    fun resetForExplicitPreparation() { rejected = false }
    fun accept(control: DriveInputControl?, renderInputValid: Boolean): Boolean {
        if (control?.source != DriveInputSource.QUALIFICATION || !control.usable || !renderInputValid) rejected = true
        return !rejected
    }
}

/** Stop drains only an already verified continuous snapshot, never a newly restored live source. */
fun selectAudioWriterSnapshot(running: Boolean, current: SoundState?, verifiedTail: SoundState?): SoundState? =
    if (running) current else verifiedTail?.copy(afterfireTrigger = false, shiftTrigger = false, shiftGain = 1.0)
