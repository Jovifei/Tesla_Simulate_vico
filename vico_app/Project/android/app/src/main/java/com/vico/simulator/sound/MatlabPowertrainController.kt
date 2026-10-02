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
)

class MatlabPowertrainController(private val spec: MatlabPowertrainSpec) {
    private var gear = 1
    private var rpm = spec.idleRpm
    private var lastTimeS = Double.NaN
    private var lastShiftTimeS = Double.NEGATIVE_INFINITY
    private var shiftStartTimeS = Double.NEGATIVE_INFINITY
    private var lastThrottle = 0.0
    private var afterfireArmed = false

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
