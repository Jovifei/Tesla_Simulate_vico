package com.vico.simulator.sound

/** Engineering candidates, NOT acoustically approved vehicle calibration. */
data class AfterfireEpisodeConfig(
    val minimumRpm: Double = 2600.0,
    val armDemand: Double = 0.25,
    val releaseDemand: Double = 0.10,
    val minimumDemandDrop: Double = 0.24,
    val armDwellS: Double = 0.150,
    val releaseDwellS: Double = 0.080,
    val refractoryS: Double = 0.350,
    val maximumFreshSampleGapS: Double = 0.250,
) {
    init {
        require(listOf(minimumRpm, armDemand, releaseDemand, minimumDemandDrop,
            armDwellS, releaseDwellS, refractoryS, maximumFreshSampleGapS).all { it.isFinite() })
        require(minimumRpm > 0.0 && releaseDemand >= 0.0 && releaseDemand < armDemand && armDemand <= 1.0)
        require(minimumDemandDrop > 0.0 && minimumDemandDrop <= 1.0)
        require(armDwellS > 0.0 && releaseDwellS > 0.0 && refractoryS >= 0.0 && maximumFreshSampleGapS > 0.0)
    }
}

/** Explicit validity has no default; caller must qualify GPS AND vehicle-frame IMU. */
data class AfterfireEpisodeInput(
    val sourceTimeS: Double,
    val sourceSequence: Long,
    val epoch: Long,
    val trusted: Boolean,
    val rpm: Double,
    val demand: Double,
    /** A strictly increasing, epoch-scoped ID for an actual qualified gear transition. */
    val shiftEventId: Long? = null,
    /** Monotonic control observation time for this actual shift, independent of IMU sample time. */
    val shiftTimeS: Double? = null,
    /** REAL demand callers require an independently qualified negative-acceleration episode. */
    val releaseEligible: Boolean = true,
    /** Pending negative-acceleration qualification; false means the low episode must be consumed. */
    val releaseIntentObserved: Boolean = true,
)

enum class AfterfireCause { QUALIFIED_RELEASE, QUALIFIED_SHIFT }
data class QualifiedAfterfireEvent(val epoch: Long, val sourceSequence: Long, val timeS: Double, val cause: AfterfireCause)

/** Control-thread confined. Never modifies PCM, reference renderers, or gear state. */
class QualifiedAfterfirePolicy(private val config: AfterfireEpisodeConfig) {
    private enum class Phase { UNARMED, ARMING, ARMED, RELEASING, REFRACTORY }
    private var phase = Phase.UNARMED
    private var epoch: Long? = null
    private var lastTimeS = Double.NaN
    private var lastSequence = Long.MIN_VALUE
    private var lastShiftId = Long.MIN_VALUE
    private var phaseStartS = Double.NaN
    private var armPeak = 0.0
    private var needsBaseline = true
    private var refractoryUntilS = Double.NEGATIVE_INFINITY

    /** Call immediately on lost trust, not just on the next valid sample. */
    fun invalidate() {
        phase = Phase.UNARMED
        phaseStartS = Double.NaN
        armPeak = 0.0
        needsBaseline = true
    }

    fun update(input: AfterfireEpisodeInput): QualifiedAfterfireEvent? {
        // Epochs are monotonic within an input session; an old packet cannot reset event deduplication.
        if (epoch != null && input.epoch < epoch!!) return null
        if (input.epoch < 0L || input.sourceSequence < 0L || input.sourceTimeS < 0.0 ||
            input.shiftEventId?.let { it < 0L } == true) {
            invalidate()
            return null
        }
        if (epoch != input.epoch) {
            invalidate()
            epoch = input.epoch
            lastTimeS = Double.NaN
            lastSequence = Long.MIN_VALUE
            lastShiftId = Long.MIN_VALUE
        }
        if (!input.trusted || !input.sourceTimeS.isFinite() || !input.rpm.isFinite() ||
            !input.demand.isFinite() || input.rpm < 0.0 || input.demand !in 0.0..1.0) {
            invalidate()
            return null
        }
        // Older sources are rejected even for a shift; a mismatched sequence/time pair is not trusted as fresh.
        if (input.sourceSequence < lastSequence || lastTimeS.isFinite() && input.sourceTimeS < lastTimeS) return null
        val sameSequence = input.sourceSequence == lastSequence
        val sameTime = lastTimeS.isFinite() && input.sourceTimeS == lastTimeS
        if (sameSequence != sameTime) return null
        if (sameSequence && sameTime) {
            // A true new gearbox transition is a separate event channel. Consume it now, never on a later IMU.
            // This branch does NOT advance the last source, arming, or release dwell.
            if (needsBaseline) {
                input.shiftEventId?.let { lastShiftId = maxOf(lastShiftId, it) }
                return null
            }
            return if (consumeShift(input) && input.rpm >= config.minimumRpm)
                emit(input, AfterfireCause.QUALIFIED_SHIFT) else null
        }
        val gap = if (lastTimeS.isFinite()) input.sourceTimeS - lastTimeS else 0.0
        if (gap > config.maximumFreshSampleGapS) invalidate()
        lastTimeS = input.sourceTimeS
        lastSequence = input.sourceSequence
        val high = input.rpm >= config.minimumRpm && input.demand >= config.armDemand
        if (needsBaseline) {
            needsBaseline = false
            input.shiftEventId?.let { lastShiftId = maxOf(lastShiftId, it) }
            if (high && cooldownComplete(input.sourceTimeS)) beginArming(input)
            return null
        }
        val freshShift = consumeShift(input)
        // Preserve real shift transients independently of release dwell and merge simultaneous causes.
        if (freshShift && input.rpm >= config.minimumRpm) return emit(input, AfterfireCause.QUALIFIED_SHIFT)
        if (input.rpm < config.minimumRpm) {
            phase = Phase.UNARMED
            armPeak = 0.0
            return null
        }
        // Retain the minimum release cooldown across invalidation/recovery; never credit arm dwell inside it.
        if (!cooldownComplete(input.sourceTimeS)) {
            phase = Phase.REFRACTORY
            return null
        }
        if (phase == Phase.REFRACTORY) phase = Phase.UNARMED
        when (phase) {
            Phase.UNARMED -> if (high) beginArming(input)
            Phase.ARMING -> {
                if (!high) { phase = Phase.UNARMED; armPeak = 0.0 }
                else {
                    armPeak = maxOf(armPeak, input.demand)
                    if (elapsed(input.sourceTimeS, phaseStartS, config.armDwellS)) phase = Phase.ARMED
                }
            }
            Phase.ARMED -> {
                if (!input.releaseIntentObserved && input.demand < config.armDemand) {
                    phase = Phase.UNARMED; armPeak = 0.0; return null
                }
                armPeak = maxOf(armPeak, input.demand)
                if (input.releaseEligible && qualifiedLow(input.demand)) { phase = Phase.RELEASING; phaseStartS = input.sourceTimeS }
            }
            Phase.RELEASING -> {
                if (!input.releaseIntentObserved && input.demand < config.armDemand) {
                    phase = Phase.UNARMED; armPeak = 0.0; return null
                }
                if (!input.releaseEligible || !qualifiedLow(input.demand)) { phase = Phase.ARMED; armPeak = maxOf(armPeak, input.demand) }
                else if (elapsed(input.sourceTimeS, phaseStartS, config.releaseDwellS))
                    return emit(input, AfterfireCause.QUALIFIED_RELEASE)
            }
            Phase.REFRACTORY -> Unit
        }
        return null
    }

    private fun consumeShift(input: AfterfireEpisodeInput): Boolean {
        val id = input.shiftEventId
        if (id == null || id <= lastShiftId) return false
        // Consume malformed timing too: a rejected transition must not reappear on a later source frame.
        lastShiftId = id
        val shiftTime = input.shiftTimeS
        return shiftTime != null && shiftTime.isFinite() && shiftTime >= input.sourceTimeS
    }

    private fun cooldownComplete(timeS: Double) = timeS + 1e-9 >= refractoryUntilS

    private fun qualifiedLow(demand: Double) = demand <= config.releaseDemand && armPeak - demand >= config.minimumDemandDrop
    private fun beginArming(input: AfterfireEpisodeInput) {
        phase = Phase.ARMING; phaseStartS = input.sourceTimeS; armPeak = input.demand
    }
    private fun emit(input: AfterfireEpisodeInput, cause: AfterfireCause): QualifiedAfterfireEvent {
        val eventTime = if (cause == AfterfireCause.QUALIFIED_SHIFT) requireNotNull(input.shiftTimeS) else input.sourceTimeS
        phase = Phase.REFRACTORY; phaseStartS = eventTime; armPeak = 0.0
        refractoryUntilS = maxOf(refractoryUntilS, eventTime + config.refractoryS)
        return QualifiedAfterfireEvent(input.epoch, input.sourceSequence, eventTime, cause)
    }
    private fun elapsed(now: Double, start: Double, interval: Double) = now - start + 1e-9 >= interval
}
