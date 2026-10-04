package com.vico.simulator.sound

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

data class MatlabPowertrainSpec(
    val idleRpm: Double,
    val redlineRpm: Double,
    val gearRatios: DoubleArray,
    val finalDrive: Double,
    val wheelRadiusM: Double,
    val launchRpm: Double,
    val shiftRpm: Double,
    val shiftAttackS: Double,
    val shiftHoldS: Double,
    val shiftRecoveryS: Double,
    val shiftSettleS: Double,
    val shiftMinTorque: Double,
    val shiftReengageGain: Double,
    val minimumShiftIntervalS: Double,
    val downshiftRatio: Double,
    val speedCeilingKmh: Double,
    val afterfireMinimumRpm: Double = 2400.0,
) {
    val upshiftSpeedKmh: DoubleArray = DoubleArray(max(0, gearRatios.size - 1)) { index ->
        shiftRpm / 60.0 / (gearRatios[index] * finalDrive) *
            (2.0 * PI * wheelRadiusM) * 3.6
    }
    val totalShiftTimeS: Double
        get() = shiftAttackS + shiftHoldS + shiftRecoveryS + shiftSettleS
}

data class MatlabPowertrainState(
    val rpm: Double,
    val load: Double,
    val gear: Int,
    val torqueGain: Double,
    val afterfireTrigger: Boolean,
    val shiftTrigger: Boolean,
    val afterfireCauseCode: Int = 0,
    val afterfireSourceId: Long? = null,
)

class MatlabPowertrainController(private val spec: MatlabPowertrainSpec) {
    private var gear = 1
    private var rpm = spec.idleRpm
    private var lastTimeS = Double.NaN
    private var lastShiftTimeS = Double.NEGATIVE_INFINITY
    private var shiftStartTimeS = Double.NEGATIVE_INFINITY
    private var lastThrottle = 0.0
    private var afterfireArmed = false

    private var measuredEpoch: Long? = null
    private var measuredUsable = false
    private var measuredRecoveryUntilS = Double.NEGATIVE_INFINITY
    private val measuredAfterfire = QualifiedAfterfirePolicy(AfterfireEpisodeConfig(minimumRpm = spec.afterfireMinimumRpm))
    private var measuredShiftEventId = 0L

    /** Live measurements only. Unknown is never interpreted as zero-speed parking. */
    fun updateMeasured(timeS: Double, speedKmh: Double, accelerationMps2: Double, throttle: Double,
                       control: DriveInputControl): MatlabPowertrainState {
        require(control.source == DriveInputSource.REAL)
        val finite = timeS.isFinite() && speedKmh.isFinite() && accelerationMps2.isFinite() && throttle.isFinite()
        if (!control.usable || !finite) {
            measuredUsable = false
            measuredAfterfire.invalidate()
            measuredEpoch = control.epoch
            clearTransientHistory()
            return MatlabPowertrainState(rpm, 0.0, gear, 1.0, false, false)
        }
        val discontinuity = !measuredUsable || measuredEpoch != control.epoch ||
            lastTimeS.isFinite() && timeS < lastTimeS
        measuredUsable = true
        measuredEpoch = control.epoch
        if (discontinuity) {
            clearTransientHistory()
            val speed = speedKmh.coerceIn(0.0, spec.speedCeilingKmh)
            // Re-anchor within existing hysteresis, not a fabricated sequence of shifts.
            while (gear < spec.gearRatios.size && speed >= spec.upshiftSpeedKmh[gear - 1]) gear++
            while (gear > 1 && speed <= spec.downshiftRatio * spec.upshiftSpeedKmh[gear - 2]) gear--
            val wheelRpm = speed / 3.6 / (2.0 * PI * spec.wheelRadiusM) * 60.0
            rpm = (wheelRpm * spec.finalDrive * spec.gearRatios[gear - 1]).coerceIn(spec.idleRpm, spec.redlineRpm)
            lastTimeS = timeS
            lastShiftTimeS = timeS
            measuredRecoveryUntilS = timeS + spec.minimumShiftIntervalS
            measuredAfterfire.invalidate()
            lastThrottle = throttle.coerceIn(0.0, 1.0)
            return MatlabPowertrainState(rpm, lastThrottle, gear, 1.0, false, false)
        }
        val state = update(timeS, speedKmh, accelerationMps2, throttle)
        if (timeS < measuredRecoveryUntilS) {
            // Refresh baselines, but do not defer a release from the uncertain interval.
            afterfireArmed = false
            measuredAfterfire.invalidate()
            return state.copy(afterfireTrigger = false, shiftTrigger = false)
        }
        if (state.shiftTrigger) measuredShiftEventId++
        val sourceNs = control.imuSampleElapsedNanos
        val event = measuredAfterfire.update(AfterfireEpisodeInput(
            sourceTimeS = (sourceNs ?: 0L) / 1_000_000_000.0,
            sourceSequence = sourceNs ?: 0L,
            epoch = control.epoch,
            trusted = control.usable && sourceNs != null && sourceNs > 0L &&
                control.gpsSampleElapsedNanos?.let { it > 0L } == true,
            rpm = state.rpm, demand = throttle.coerceIn(0.0, 1.0),
            shiftEventId = measuredShiftEventId.takeIf { state.shiftTrigger },
            shiftTimeS = if (state.shiftTrigger) control.controlTimeElapsedNanos?.div(1_000_000_000.0) else null,
        ))
        // Never OR the old sample-to-sample trigger back into the qualified measured policy.
        val cause = when (event?.cause) {
            AfterfireCause.QUALIFIED_RELEASE -> 1
            AfterfireCause.QUALIFIED_SHIFT -> 2
            null -> 0
        }
        return state.copy(afterfireTrigger = event != null, afterfireCauseCode = cause,
            afterfireSourceId = if (event?.cause == AfterfireCause.QUALIFIED_SHIFT) control.gpsSampleElapsedNanos
                else event?.sourceSequence)
    }

    private fun clearTransientHistory() {
        shiftStartTimeS = Double.NEGATIVE_INFINITY
        afterfireArmed = false
        lastThrottle = 0.0
    }

    fun update(timeS: Double, speedKmh: Double, accelerationMps2: Double, throttle: Double): MatlabPowertrainState {
        val speed = speedKmh.coerceIn(0.0, spec.speedCeilingKmh)
        val dt = if (lastTimeS.isFinite()) (timeS - lastTimeS).coerceIn(0.001, 0.2) else 0.05
        lastTimeS = timeS
        val canShift = timeS - lastShiftTimeS >= spec.minimumShiftIntervalS
        var shifted = false
        if (canShift && accelerationMps2 > 0.15 && gear < spec.gearRatios.size &&
            speed >= spec.upshiftSpeedKmh[gear - 1]) {
            gear++
            shifted = true
        } else if (canShift && accelerationMps2 < -0.15 && gear > 1 &&
            speed <= spec.downshiftRatio * spec.upshiftSpeedKmh[gear - 2]) {
            gear--
            shifted = true
        }
        if (shifted) {
            lastShiftTimeS = timeS
            shiftStartTimeS = timeS
        }

        val elapsed = timeS - shiftStartTimeS
        val (torqueGain, coupling) = shiftState(elapsed)
        val speedMps = speed / 3.6
        val wheelRpm = speedMps / (2.0 * PI * spec.wheelRadiusM) * 60.0
        val targetRpm = max(spec.idleRpm, wheelRpm * spec.finalDrive * spec.gearRatios[gear - 1])
        rpm = if (elapsed in 0.0..spec.totalShiftTimeS) {
            val adjusted = 1.0 - (1.0 - coupling).pow(max(1.0, dt * 1000.0))
            rpm + adjusted * (targetRpm - rpm)
        } else {
            targetRpm
        }
        val launchBlend = min(1.0, speedMps / 4.0)
        val launchSlip = spec.idleRpm + throttle * (spec.launchRpm - spec.idleRpm) * (1.0 - launchBlend)
        rpm = min(spec.redlineRpm, max(rpm, launchSlip))
        val load = (throttle * torqueGain).coerceIn(0.0, 1.0)
        if (rpm >= spec.afterfireMinimumRpm && throttle >= 0.25) afterfireArmed = true
        val afterfire = rpm >= spec.afterfireMinimumRpm && (
            shifted || lastThrottle - throttle > 0.24 || accelerationMps2 < -1.2 && afterfireArmed
            )
        if (afterfire) afterfireArmed = false
        lastThrottle = throttle
        return MatlabPowertrainState(rpm, load, gear, torqueGain, afterfire, shifted)
    }

    private fun shiftState(elapsed: Double): Pair<Double, Double> = when {
        !elapsed.isFinite() || elapsed < 0.0 -> 1.0 to 1.0
        elapsed < spec.shiftAttackS -> {
            val progress = elapsed / spec.shiftAttackS
            cosineBlend(1.0, spec.shiftMinTorque, progress) to (0.08 + 0.18 * progress)
        }
        elapsed < spec.shiftAttackS + spec.shiftHoldS -> spec.shiftMinTorque to 0.22
        elapsed < spec.shiftAttackS + spec.shiftHoldS + spec.shiftRecoveryS -> {
            val progress = (elapsed - spec.shiftAttackS - spec.shiftHoldS) / spec.shiftRecoveryS
            cosineBlend(spec.shiftMinTorque, spec.shiftReengageGain, progress) to (0.24 + 0.56 * progress)
        }
        elapsed < spec.totalShiftTimeS -> {
            val progress = (elapsed - spec.shiftAttackS - spec.shiftHoldS - spec.shiftRecoveryS) / spec.shiftSettleS
            cosineBlend(spec.shiftReengageGain, 1.0, progress) to (0.80 + 0.20 * progress)
        }
        else -> 1.0 to 1.0
    }

    private fun cosineBlend(start: Double, finish: Double, progress: Double): Double {
        val blend = 0.5 - 0.5 * cos(PI * progress.coerceIn(0.0, 1.0))
        return start + (finish - start) * blend
    }
}
