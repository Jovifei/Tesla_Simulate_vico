package com.vico.simulator.sound

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * 纯 Kotlin 声浪模型，1:1 移植自 `E:\Tesla_speed\prj\tools\sound_sim\sound_model.py` (SoundModel)。
 * 可无 Android 硬件测试（PRD NFR-05）。Sport 档输出与 Python 参考轨迹逐行一致（AC-06 可追溯）。
 *
 * 算法: speed/throttle/accel/brake -> 平滑虚拟 RPM -> 基频 + 5 谐波加法合成 -> int16 PCM。
 */
data class DrivePoint(
    val timeS: Double,
    val speedKmh: Double,
    val throttle: Double,
    val accelMps2: Double,
    val brake: Boolean = false,
)

enum class DriveInputSource { UNSPECIFIED, REAL, DEMO, PREVIEW, QUALIFICATION }

/** Explicit live control contract. Nullable only on old standalone reference fixtures. */
data class DriveInputControl(
    val source: DriveInputSource,
    val epoch: Long,
    val validUntilElapsedNanos: Long,
    val speedUsable: Boolean,
    val accelerationUsable: Boolean,
    val imuSampleElapsedNanos: Long? = null,
    val gpsSampleElapsedNanos: Long? = null,
    val controlFrameId: Long? = null,
    val controlTimeElapsedNanos: Long? = null,
    /** REAL model segment identity, separate from upstream measurement/source epoch. */
    val modelContinuityRevision: Long = 0L,
    /** Provider reported speed uncertainty at the GPS sample; null remains unverified. */
    val reportedSpeedUncertaintyMps: Double? = null,
) {
    val usable: Boolean get() = speedUsable && accelerationUsable
    fun validatedFor(point: DrivePoint): DriveInputControl =
        if (point.timeS.isFinite() && point.speedKmh.isFinite() && point.speedKmh >= 0.0 &&
            point.throttle.isFinite() && point.accelMps2.isFinite() &&
            reportedSpeedUncertaintyMps?.let { it.isFinite() && it >= 0.0 } != false) this
        else copy(speedUsable = false, accelerationUsable = false)
}

data class SoundState(
    val timeS: Double,
    val rpm: Double,
    val frequencyHz: Double,
    val amplitude: Double,
    val brightness: Double,
    val harmonics: FloatArray,
    val muted: Boolean,
    val throttle: Double = 0.0,
    val load: Double = 0.0,
    val braking: Boolean = false,
    val gear: Int = 1,
    val shiftGain: Double = 1.0,
    val afterfireTrigger: Boolean = false,
    val shiftTrigger: Boolean = false,
    val inputControl: DriveInputControl? = null,
    val afterfireCauseCode: Int = 0,
    val afterfireSourceId: Long? = null,
    val modelSpeedKmh: Double? = null,
    val modelAccelerationMps2: Double? = null,
) {
    override fun equals(other: Any?): Boolean = this === other
    override fun hashCode(): Int = System.identityHashCode(this)
}

class SoundModel(private val smoothing: Double = DEFAULT_SMOOTHING) {

    private var smoothRpm: Double = IDLE_RPM
    private var phase: Double = 0.0

    /** 对应 Python SoundModel.map_point。profile=SPORT 时与 Python 输出一致。 */
    fun mapPoint(point: DrivePoint, profile: SoundProfile = SoundProfile.DEFAULT): SoundState {
        val idle = profile.idleRpm
        val maxR = profile.maxRpm
        val throttle = clamp(point.throttle, 0.0, 1.0)
        val speed = max(0.0, point.speedKmh)
        val positiveAccel = clamp(point.accelMps2 / 3.0, 0.0, 1.0)
        val braking = point.brake || point.accelMps2 < -1.2

        val speedRpm = idle + clamp(speed / 180.0, 0.0, 1.0) * (SPEED_RPM_CEIL - idle)
        val throttleFactor = 0.30 + 0.70 * throttle
        var targetRpm = idle + (speedRpm - idle) * throttleFactor
        targetRpm += positiveAccel * 850.0
        if (braking) targetRpm = max(idle, targetRpm * 0.45)
        targetRpm = clamp(targetRpm, idle, maxR)

        smoothRpm += smoothing * (targetRpm - smoothRpm)

        val rpmNorm = clamp((smoothRpm - idle) / (maxR - idle), 0.0, 1.0)
        var brightness = clamp(0.20 + throttle * 0.45 + positiveAccel * 0.35, 0.0, 1.0)
        var amplitude = clamp(0.12 + throttle * 0.32 + positiveAccel * 0.18, 0.0, 0.72)
        if (braking) {
            brightness *= 0.55
            amplitude *= 0.65
        }

        // 档位风格: 亮度缩放
        brightness = clamp(brightness * profile.brightScale, 0.0, 1.0)

        // 基础 5 谐波 (对应 Python), 再按档位形状加权
        val baseH = doubleArrayOf(
            1.00,
            clamp(0.34 + brightness * 0.26, 0.0, 1.0),
            clamp(0.12 + brightness * 0.35, 0.0, 1.0),
            clamp(0.05 + positiveAccel * 0.22, 0.0, 1.0),
            clamp(0.025 + throttle * 0.10, 0.0, 1.0),
        )
        val harmonics = FloatArray(5) { i ->
            clamp(baseH[i] * profile.harmonicWeights[i], 0.0, 1.0).toFloat()
        }

        val frequencyHz = 40.0 + rpmNorm * 180.0
        val muted = speed >= OVERSPEED_MUTE_KMH
        return SoundState(
            timeS = point.timeS,
            rpm = smoothRpm,
            frequencyHz = frequencyHz,
            amplitude = if (muted) 0.0 else amplitude,
            brightness = brightness,
            harmonics = harmonics,
            muted = muted,
        )
    }

    /** 对应 Python SoundModel.render_state: 加法合成 -> int16 PCM 帧。 */
    fun renderState(state: SoundState, frameCount: Int, sampleRate: Int = SAMPLE_RATE): ShortArray {
        if (state.muted || state.amplitude <= 0.0) {
            return ShortArray(frameCount)
        }
        val out = ShortArray(frameCount)
        var norm = 0.0
        for (g in state.harmonics) norm += abs(g)
        val amplitude = state.amplitude * 0.78 / max(norm, 1.0)
        val dphi = 2.0 * PI * state.frequencyHz / sampleRate
        for (i in 0 until frameCount) {
            var sample = 0.0
            for (idx in state.harmonics.indices) {
                sample += state.harmonics[idx] * sin(phase * (idx + 1))
            }
            val v = (clamp(sample * amplitude, -1.0, 1.0) * 32767.0).toInt()
            out[i] = v.toShort()
            phase += dphi
            if (phase >= 2.0 * PI) phase -= 2.0 * PI
        }
        return out
    }

    companion object {
        const val SAMPLE_RATE: Int = 44100
        const val DEFAULT_SMOOTHING: Double = 0.18
        const val IDLE_RPM: Double = 800.0
        const val MAX_RPM: Double = 6800.0
        const val SPEED_RPM_CEIL: Double = 6000.0
        const val OVERSPEED_MUTE_KMH: Double = 150.0
    }
}

private fun clamp(v: Double, lo: Double, hi: Double): Double = max(lo, min(hi, v))
