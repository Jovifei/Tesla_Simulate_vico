package com.vico.simulator.sound

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.tanh

/**
 * 参数化车型声浪合成器。per-cylinder 排气模型 + 谐波层 + 排气谐振 + turbo 层。
 *
 * 算法 (参考 tesla-engine-sound per-cylinder 排气阀 + Engine-Sound-Simulator 点火时序):
 * - 曲轴相位 cyclePhase 按 rpm 推进, 每缸在 firingTiming 处点火
 * - 排气阀窗内指数衰减脉冲 -> 多缸求和 -> 1 抽头高通排气谐振
 * - 叠加点火基频谐波层 + (可选) turbo 正弦层
 * - tanh 软限幅 + 主音量
 *
 * 全参数化: [VehicleProfile] 即车型; MATLAB 调参 = App 播放 (parity 可校验)。
 */
class VehicleSoundModel(profile: VehicleProfile = VehicleProfile.DEFAULT) {

    var profile: VehicleProfile = profile
        set(value) {
            field = value
            resetForProfile(value)
        }

    /** Soft/Sport/Sci-Fi 强度修饰 (仪表盘选择); 叠加在车型之上。SPORT=恒等 (保 parity)。 */
    var character: SoundProfile = SoundProfile.DEFAULT

    private var smoothRpm: Double = profile.idleRpm
    private var cyclePhase: Double = 0.0
    private var harmPhase: Double = 0.0
    private var turboPhase: Double = 0.0
    private var inductionPhase: Double = 0.0
    private var mechanicalPhase: Double = 0.0
    private var prevPulse: Double = 0.0
    private val rnd = java.util.Random(0xC0FFEE)
    private var currentGear = 1
    private var shiftRemainingS = 0.0
    private var lastTimeS = Double.NaN
    private var lastThrottle = 0.0
    private var afterfireArmed = false
    private var lastEventSlot = -1
    private var correlatedCombustion = 0.0
    private var eventGain = 1.0
    private var afterfirePending = 0
    private var afterfireCountdown = 0
    private var previousCrackNoise = 0.0
    private var consumedAfterfireTimeS = Double.NaN
    private val activeBursts = mutableListOf<AfterfireBurst>()
    private var modeX1 = DoubleArray(0)
    private var modeX2 = DoubleArray(0)
    private var modeY1 = DoubleArray(0)
    private var modeY2 = DoubleArray(0)

    init {
        resetForProfile(profile)
    }

    /** 速度/油门/加速度 -> 平滑 RPM + 振幅 + 亮度 + (character 修饰后的) 谐波。 */
    fun mapPoint(point: DrivePoint): SoundState {
        val p = profile
        val idle = p.idleRpm
        val red = p.redlineRpm
        val throttle = clamp(point.throttle, 0.0, 1.0)
        val rawSpeed = max(0.0, point.speedKmh)
        val speed = p.driveline?.let { min(rawSpeed, it.speedCeilingKmh) } ?: rawSpeed
        val positiveAccel = clamp(point.accelMps2 / 3.0, 0.0, 1.0)
        val braking = point.brake || point.accelMps2 < -1.2
        val dt = if (lastTimeS.isFinite()) (point.timeS - lastTimeS).coerceIn(0.005, 0.1) else 0.05
        lastTimeS = point.timeS
        val shiftStarted = updateGear(speed)
        val targetRpm = targetRpm(speed, throttle, positiveAccel, braking)
        val smoothing = 1.0 - exp(-dt / if (braking) 0.16 else 0.11)
        smoothRpm += smoothing * (targetRpm - smoothRpm)
        val shiftGain = currentShiftGain(dt)
        val afterfire = p.afterfire
        if (afterfire != null && smoothRpm >= afterfire.minimumRpm && throttle >= 0.25) {
            afterfireArmed = true
        }
        val lifted = afterfire != null && smoothRpm >= afterfire.minimumRpm &&
            (lastThrottle - throttle >= afterfire.throttleDrop || braking && afterfireArmed)
        if (lifted) afterfireArmed = false
        val afterfireTrigger = lifted || (shiftStarted && afterfire != null && smoothRpm >= afterfire.minimumRpm)
        lastThrottle = throttle

        var clampedRpm = clamp(smoothRpm, idle, red)
        if (!clampedRpm.isFinite()) clampedRpm = idle
        smoothRpm = clampedRpm

        var brightness = clamp(0.20 + throttle * 0.45 + positiveAccel * 0.35, 0.0, 1.0)
        var amplitude = clamp(0.12 + throttle * 0.32 + positiveAccel * 0.18, 0.0, 0.72)
        if (braking) { brightness *= 0.55; amplitude *= 0.65 }

        // character 修饰: 亮度缩放 + 谐波形状加权 (SPORT = 恒等, 保 MATLAB parity)
        brightness = clamp(brightness * character.brightScale, 0.0, 1.0)
        val harmonics = FloatArray(min(profile.harmonics.size, character.harmonicWeights.size)) { i ->
            clamp((profile.harmonics[i] * character.harmonicWeights[i]).toDouble(), 0.0, 1.0).toFloat()
        }

        // 点火基频 (ICE) 或电机频率 (EV: motorFreqMult>0)
        val fFire = if (profile.motorFreqMult > 0.0)
            (smoothRpm / 60.0) * p.motorFreqMult
        else
            (smoothRpm / 60.0) * p.firesPerRev
        val muted = rawSpeed >= p.overspeedMuteKmh
        return SoundState(
            timeS = point.timeS,
            rpm = smoothRpm,
            frequencyHz = fFire,
            // Keep the source amplitude available so AudioEngine can fade an overspeed mute
            // instead of cutting the PCM stream in the same block.
            amplitude = amplitude,
            brightness = brightness,
            harmonics = harmonics,
            muted = muted,
            throttle = throttle,
            load = clamp(0.16 + 0.62 * throttle + 0.22 * positiveAccel, 0.0, 1.0),
            braking = braking,
            gear = currentGear,
            shiftGain = shiftGain,
            afterfireTrigger = afterfireTrigger,
        )
    }

    /** per-cylinder 排气合成 -> int16 PCM。 */
    fun renderState(state: SoundState, frameCount: Int, sampleRate: Int = 44100): ShortArray {
        val out = ShortArray(frameCount)
        if (state.muted || state.amplitude <= 0.0) return out

        val p = profile
        val crankFreq = state.rpm / 60.0                          // 曲轴 rev/s
        val dPhase = 2.0 * PI * crankFreq / sampleRate            // 每样本曲轴角增量
        val fFire = state.frequencyHz                             // mapPoint 已算 (ICE 点火基频 / EV 电机频率)
        val dHarm = 2.0 * PI * fFire / sampleRate
        val cycle = p.cycleAngle
        val window = p.exhaustWindow * cycle
        val norm = max(p.cylinders / 2.0, 1.0)
        val throttle = 0.5 + 0.5 * state.brightness
        val turbo = p.turbo

        for (i in 0 until frameCount) {
            cyclePhase += dPhase
            if (cyclePhase >= cycle) cyclePhase -= cycle

            updateCombustionEvent(p, state)

            // --- per-cylinder 排气脉冲 ---
            var pulse = 0.0
            for (c in 0 until p.cylinders) {
                var d = cyclePhase - p.firingTiming[c]
                if (d < 0.0) d += cycle
                if (d < window) {
                    pulse += exp(-d / p.decayRad)
                }
            }
            pulse = pulse / norm * throttle * eventGain
            pulse *= 1.0 + (rnd.nextDouble() - 0.5) * p.combJitter

            // --- 排气谐振 (1 抽头高通) ---
            val exhaust = pulse - p.exhaustResonance * prevPulse
            prevPulse = pulse

            // --- 谐波层 ---
            harmPhase += dHarm
            if (harmPhase >= 2.0 * PI) harmPhase -= 2.0 * PI
            var harm = 0.0
            for (h in state.harmonics.indices) {
                if (h >= p.harmMult.size) break
                harm += state.harmonics[h] * wave(p.waveform, p.harmMult[h] * harmPhase)
            }

            // --- 混合 (EV: cylinders=0 纯谐波) ---
            val body = renderBodyModes(exhaust, p.bodyModes, sampleRate)
            val rasp = p.raspGain * (tanh(exhaust * 3.0) - exhaust)
            var main = if (p.cylinders <= 0) harm else
                exhaust * p.exhaustGain + body + harm * p.harmonicGain + rasp

            // --- turbo 层 ---
            if (turbo != null && state.rpm > turbo.thresholdRpm) {
                val tGain = clamp((state.rpm - turbo.thresholdRpm) / max(p.redlineRpm - turbo.thresholdRpm, 1.0), 0.0, 1.0)
                turboPhase += 2.0 * PI * fFire * turbo.freqMult / sampleRate
                if (turboPhase >= 2.0 * PI) turboPhase -= 2.0 * PI
                main += turbo.gain * tGain * sin(turboPhase)
            }

            val induction = renderInduction(p, state, sampleRate)
            val mechanical = renderMechanical(p, state, sampleRate)
            val afterfireSample = renderAfterfire(p, state, sampleRate)

            // --- 软限幅 + 振幅 ---
            val shiftedMain = main * state.shiftGain
            val v = tanh(((shiftedMain + induction + mechanical) * state.amplitude + afterfireSample) * p.softClipDrive)
            out[i] = (v * 32767.0).toInt().coerceIn(-32768, 32767).toShort()
        }
        return out
    }

    private fun targetRpm(speedKmh: Double, throttle: Double, positiveAccel: Double, braking: Boolean): Double {
        val p = profile
        val driveline = p.driveline
        if (driveline == null || driveline.gearRatios.isEmpty()) {
            val speedRpm = p.idleRpm + clamp(speedKmh / 180.0, 0.0, 1.0) * (6000.0 - p.idleRpm)
            var rpm = p.idleRpm + (speedRpm - p.idleRpm) * (0.30 + 0.70 * throttle) + positiveAccel * 850.0
            if (braking) rpm = max(p.idleRpm, rpm * 0.45)
            return clamp(rpm, p.idleRpm, p.redlineRpm)
        }
        val wheelRpm = speedKmh / 3.6 / (2.0 * PI * driveline.wheelRadiusM) * 60.0
        val coupled = wheelRpm * driveline.gearRatios[currentGear - 1] * driveline.finalDrive
        val launch = p.idleRpm + throttle * (driveline.launchRpm - p.idleRpm)
        val freeRev = p.idleRpm + throttle.pow(0.72) * (p.redlineRpm - p.idleRpm) * 0.34
        val rpm = if (speedKmh < 4.0) max(launch, freeRev) else max(coupled, p.idleRpm + positiveAccel * 260.0)
        return clamp(rpm, p.idleRpm, p.redlineRpm)
    }

    private fun updateGear(speedKmh: Double): Boolean {
        val d = profile.driveline ?: return false
        if (d.gearRatios.isEmpty()) return false
        val speed = speedKmh.coerceIn(0.0, d.speedCeilingKmh)
        var shifted = false
        if (d.upshiftSpeedKmh.isNotEmpty()) {
            while (currentGear < d.gearRatios.size && currentGear <= d.upshiftSpeedKmh.size &&
                speed >= d.upshiftSpeedKmh[currentGear - 1]) {
                currentGear++
                shifted = true
            }
            while (currentGear > 1 && currentGear - 2 < d.downshiftSpeedKmh.size &&
                speed < d.downshiftSpeedKmh[currentGear - 2]) {
                currentGear--
                shifted = true
            }
        } else {
            val wheelRpm = speed / 3.6 / (2.0 * PI * d.wheelRadiusM) * 60.0
            while (currentGear < d.gearRatios.size &&
                wheelRpm * d.gearRatios[currentGear - 1] * d.finalDrive >= d.shiftRpm) {
                currentGear++
                shifted = true
            }
            while (currentGear > 1 &&
                wheelRpm * d.gearRatios[currentGear - 1] * d.finalDrive < profile.idleRpm * 1.18) {
                currentGear--
                shifted = true
            }
        }
        if (shifted) shiftRemainingS = d.shiftDurationS
        return shifted
    }

    private fun currentShiftGain(dt: Double): Double {
        val d = profile.driveline ?: return 1.0
        if (shiftRemainingS <= 0.0) return 1.0
        val progress = 1.0 - shiftRemainingS / max(d.shiftDurationS, 0.001)
        shiftRemainingS = max(0.0, shiftRemainingS - dt)
        return when {
            progress < 0.30 -> 1.0 + (d.shiftMinGain - 1.0) * progress / 0.30
            progress < 0.62 -> d.shiftMinGain
            else -> d.shiftMinGain + (1.0 - d.shiftMinGain) * (progress - 0.62) / 0.38
        }.coerceIn(d.shiftMinGain, 1.0)
    }

    private fun updateCombustionEvent(p: VehicleProfile, state: SoundState) {
        if (p.cylinders <= 0) return
        val slot = floor(cyclePhase / p.cycleAngle * p.cylinders).toInt().coerceIn(0, p.cylinders - 1)
        if (slot == lastEventSlot) return
        lastEventSlot = slot
        val spec = p.combustionVariation ?: run { eventGain = 1.0; return }
        val rpmGate = clamp((state.rpm - spec.startRpm) / max(spec.fullRpm - spec.startRpm, 1.0), 0.0, 1.0)
        val gate = rpmGate * clamp((state.load - 0.18) / 0.82, 0.0, 1.0)
        val innovation = rnd.nextGaussian()
        correlatedCombustion = spec.correlation * correlatedCombustion + (1.0 - spec.correlation) * innovation
        var gain = 1.0 + spec.depth * correlatedCombustion
        if (rnd.nextDouble() < spec.notchProbability) gain *= 1.0 - spec.notchDepth * (0.65 + 0.35 * rnd.nextDouble())
        if (spec.cylinderGain.isNotEmpty()) gain *= spec.cylinderGain[slot % spec.cylinderGain.size]
        gain = clamp(gain, spec.minimumGain, spec.maximumGain)
        eventGain = 1.0 + gate * (gain - 1.0)
    }

    private fun renderBodyModes(input: Double, modes: List<BodyModeSpec>, sampleRate: Int): Double {
        var output = 0.0
        for (index in modes.indices) {
            val mode = modes[index]
            val radius = exp(-PI * mode.frequencyHz / max(mode.q * sampleRate, 1.0))
            val a1 = -2.0 * radius * cos(2.0 * PI * mode.frequencyHz / sampleRate)
            val a2 = radius * radius
            val b = 1.0 - radius
            val y = b * (input - modeX2[index]) - a1 * modeY1[index] - a2 * modeY2[index]
            modeX2[index] = modeX1[index]
            modeX1[index] = input
            modeY2[index] = modeY1[index]
            modeY1[index] = y
            output += mode.gain * y
        }
        return output
    }

    private fun renderInduction(p: VehicleProfile, state: SoundState, sampleRate: Int): Double {
        val spec = p.induction ?: return 0.0
        if (state.rpm <= spec.startRpm) return 0.0
        inductionPhase = (inductionPhase + 2.0 * PI * state.rpm / 60.0 * spec.speedRatio / sampleRate) % (2.0 * PI)
        val gate = clamp((state.rpm - spec.startRpm) / max(p.redlineRpm - spec.startRpm, 1.0), 0.0, 1.0).pow(0.8) * state.load.pow(1.25)
        var output = 0.0
        for (i in 0 until min(spec.orders.size, spec.gains.size)) output += spec.gains[i] * sin(spec.orders[i] * inductionPhase)
        return output * gate
    }

    private fun renderMechanical(p: VehicleProfile, state: SoundState, sampleRate: Int): Double {
        val spec = p.mechanical ?: return 0.0
        mechanicalPhase = (mechanicalPhase + 2.0 * PI * state.rpm / 60.0 / sampleRate) % (2.0 * PI)
        var output = 0.0
        for (i in 0 until min(spec.orders.size, spec.gains.size)) output += spec.gains[i] * sin(spec.orders[i] * mechanicalPhase)
        return output * state.load
    }

    private fun renderAfterfire(p: VehicleProfile, state: SoundState, sampleRate: Int): Double {
        val spec = p.afterfire ?: return 0.0
        val newTrigger = state.afterfireTrigger && state.timeS != consumedAfterfireTimeS
        if (newTrigger) consumedAfterfireTimeS = state.timeS
        if (newTrigger && afterfirePending == 0 && activeBursts.isEmpty()) {
            afterfirePending = spec.clusterSize.coerceAtLeast(1)
            afterfireCountdown = 0
        }
        if (afterfirePending > 0) {
            if (afterfireCountdown <= 0) {
                val progress = 1.0 - afterfirePending.toDouble() / spec.clusterSize.coerceAtLeast(1)
                activeBursts += AfterfireBurst(
                    strength = 0.78 - 0.38 * progress,
                    bodyPhase = rnd.nextDouble() * 2.0 * PI,
                    metalPhase = rnd.nextDouble() * 2.0 * PI,
                )
                afterfirePending--
                afterfireCountdown = (spec.intervalS * sampleRate * (0.82 + 0.36 * rnd.nextDouble())).toInt()
            } else afterfireCountdown--
        }
        var output = 0.0
        val iterator = activeBursts.iterator()
        while (iterator.hasNext()) {
            val burst = iterator.next()
            val t = burst.ageSamples / sampleRate.toDouble()
            val duration = max(0.055, 7.0 * spec.bodyDecayS)
            if (t > duration) { iterator.remove(); continue }
            val attack = min(1.0, t / 0.0015)
            var body = 0.0
            for (f in spec.bodyHz) body += sin(2.0 * PI * f * t + burst.bodyPhase)
            body /= max(spec.bodyHz.size, 1)
            var metal = 0.0
            for (f in spec.metalHz) metal += sin(2.0 * PI * f * t + burst.metalPhase)
            metal /= max(spec.metalHz.size, 1)
            val noise = rnd.nextDouble() * 2.0 - 1.0
            val crack = noise - previousCrackNoise
            previousCrackNoise = noise
            output += burst.strength * attack * (
                spec.bodyGain * exp(-t / spec.bodyDecayS) * body +
                    spec.metalGain * exp(-t / spec.metalDecayS) * metal +
                    spec.crackGain * exp(-t / spec.crackDecayS) * crack
                )
            burst.ageSamples++
        }
        return output * 0.42
    }

    private fun resetForProfile(p: VehicleProfile) {
        smoothRpm = p.idleRpm
        cyclePhase = 0.0
        harmPhase = 0.0
        turboPhase = 0.0
        inductionPhase = 0.0
        mechanicalPhase = 0.0
        prevPulse = 0.0
        currentGear = 1
        shiftRemainingS = 0.0
        lastTimeS = Double.NaN
        lastThrottle = 0.0
        afterfireArmed = false
        lastEventSlot = -1
        correlatedCombustion = 0.0
        eventGain = 1.0
        afterfirePending = 0
        afterfireCountdown = 0
        consumedAfterfireTimeS = Double.NaN
        activeBursts.clear()
        modeX1 = DoubleArray(p.bodyModes.size)
        modeX2 = DoubleArray(p.bodyModes.size)
        modeY1 = DoubleArray(p.bodyModes.size)
        modeY2 = DoubleArray(p.bodyModes.size)
    }

    private data class AfterfireBurst(
        val strength: Double,
        val bodyPhase: Double,
        val metalPhase: Double,
        var ageSamples: Int = 0,
    )

    private fun wave(type: String, phase: Double): Double {
        val x = phase % (2.0 * PI)
        return when (type) {
            "square" -> if (sin(x) >= 0.0) 1.0 else -1.0
            "saw", "sawtooth" -> 2.0 * (x / (2.0 * PI)) - 1.0
            else -> sin(x)   // sine
        }
    }

    private fun clamp(v: Double, lo: Double, hi: Double): Double = max(lo, min(hi, v))
}
