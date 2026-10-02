package com.vico.simulator.sound

import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.PI

/**
 * 车型声浪档案。schema: `vico.vehicle.v1`。
 *
 * MATLAB 离线调参 -> 导出 JSON -> App 运行时解析 -> [VehicleSoundModel] 合成。
 * 参考: tesla-engine-sound (per-cylinder 排气阀包络 + IR 段混合)、
 *       Engine-Sound-Simulator (cylinders/stroke/firing_timing/unequal)。
 *
 * 合成模型: 每缸按 [firingTiming] 在曲轴周期内点火，排气阀窗内指数衰减脉冲 ->
 * 多缸求和 -> 排气谐振 1 抽头高通 -> 叠加谐波层 + turbo 层。
 */
data class VehicleProfile(
    val name: String,
    val cylinders: Int,
    val stroke: Int,                    // 4 或 2 冲程
    val firingTiming: DoubleArray,      // 每缸点火曲轴角 (rad, 0..cycleAngle); 决定不均匀点火节奏
    val idleRpm: Double,
    val redlineRpm: Double,
    val harmonics: FloatArray,          // 谐波增益 (×点火基频的整数倍)
    val harmMult: IntArray,             // 谐波次数 (×fFire)
    val waveform: String,               // sine/saw/square
    val combJitter: Float,              // 燃烧随机扰动 0..1
    val exhaustResonance: Float,        // 1 抽头 HPF 系数 (如 0.97); 0=关
    val exhaustWindow: Float,           // 排气阀开窗占周期比例 (如 0.5)
    val decayRad: Float,                // 排气脉冲衰减常数 (rad)
    val turbo: LayerSpec?,
    val overspeedMuteKmh: Double,
    val character: String,              // soft/sport/scifi 强度修饰
    val motorFreqMult: Double = 0.0,    // >0 = EV 电机嗡鸣模式 (cylinders 可为 0, freq=rpm/60*motorFreqMult)
    val driveline: DrivelineSpec? = null,
    val combustionVariation: CombustionVariationSpec? = null,
    val afterfire: AfterfireSpec? = null,
    val bodyModes: List<BodyModeSpec> = emptyList(),
    val induction: InductionSpec? = null,
    val mechanical: MechanicalSpec? = null,
    val exhaustGain: Float = 0.70f,
    val harmonicGain: Float = 0.30f,
    val raspGain: Float = 0.0f,
    val softClipDrive: Float = 2.2f,
) {
    /** 曲轴周期角 (4 冲程 720°=4π, 2 冲程 360°=2π)。 */
    val cycleAngle: Double get() = if (stroke == 4) 4.0 * PI else 2.0 * PI
    /** 每曲轴转的点火次数 = cylinders × 2 / stroke (4冲程: cyl/2; 2冲程: cyl)。 */
    val firesPerRev: Double get() = cylinders.toDouble() * 2.0 / stroke.toDouble()

    companion object {
        const val SCHEMA = "vico.vehicle.v1"

        /** 从 assets/vehicles/ 下的 JSON 解析。 */
        fun fromJson(json: String): VehicleProfile {
            val o = JSONObject(json)
            val eng = o.optJSONObject("engine") ?: JSONObject()
            val syn = o.optJSONObject("synthesis") ?: JSONObject()
            val flt = o.optJSONObject("filters")
            val lay = o.optJSONObject("layers")
            val map = o.optJSONObject("mapping")
            val drivelineJson = o.optJSONObject("driveline")
            val variationJson = o.optJSONObject("combustionVariation")
            val afterfireJson = o.optJSONObject("afterfire")
            val cylinders = eng.optInt("cylinders", 8)
            val stroke = eng.optInt("stroke", 4)
            val firingTiming = eng.optJSONArray("firingOrderDegrees")?.let { arr ->
                DoubleArray(arr.length()) { arr.getDouble(it) * PI / 180.0 }
            } ?: defaultFiringTiming(cylinders, stroke)
            val harmonics = optFloatArray(syn, "harmonics", floatArrayOf(1.0f, 0.55f, 0.32f, 0.18f, 0.09f))
            val harmMult = optIntArray(syn, "harmMult", intArrayOf(1, 2, 3, 4, 5))
            val turbo = lay?.optJSONObject("turbo")?.let {
                if (it.optBoolean("enabled", true)) LayerSpec(
                    it.optDouble("freqMult", 10.0),
                    it.optDouble("gain", 0.12).toFloat(),
                    it.optDouble("thresholdRpm", 3000.0),
                ) else null
            }
            val driveline = drivelineJson?.let {
                DrivelineSpec(
                    gearRatios = optDoubleArray(it, "gearRatios", doubleArrayOf()),
                    finalDrive = it.optDouble("finalDrive", 1.0),
                    wheelRadiusM = it.optDouble("wheelRadiusM", 0.335),
                    launchRpm = it.optDouble("launchRpm", 1800.0),
                    shiftRpm = it.optDouble("shiftRpm", 6500.0),
                    shiftDurationS = it.optDouble("shiftDurationS", 0.14),
                    shiftMinGain = it.optDouble("shiftMinGain", 0.20),
                    upshiftSpeedKmh = optDoubleArray(it, "upshiftSpeedKmh", doubleArrayOf()),
                    downshiftSpeedKmh = optDoubleArray(it, "downshiftSpeedKmh", doubleArrayOf()),
                    speedCeilingKmh = it.optDouble("speedCeilingKmh", 144.0),
                )
            }
            val variation = variationJson?.let {
                CombustionVariationSpec(
                    startRpm = it.optDouble("startRpm", 1400.0),
                    fullRpm = it.optDouble("fullRpm", 5000.0),
                    depth = it.optDouble("depth", 0.0),
                    correlation = it.optDouble("correlation", 0.35),
                    notchProbability = it.optDouble("notchProbability", 0.0),
                    notchDepth = it.optDouble("notchDepth", 0.0),
                    minimumGain = it.optDouble("minimumGain", 0.5),
                    maximumGain = it.optDouble("maximumGain", 1.5),
                    cylinderGain = optFloatArray(it, "cylinderGain", FloatArray(cylinders) { 1.0f }),
                )
            }
            val afterfire = afterfireJson?.let {
                if (!it.optBoolean("enabled", true)) null else AfterfireSpec(
                    minimumRpm = it.optDouble("minimumRpm", 2400.0),
                    throttleDrop = it.optDouble("throttleDrop", 0.22),
                    clusterSize = it.optInt("clusterSize", 5),
                    intervalS = it.optDouble("intervalS", 0.06),
                    bodyHz = optFloatArray(it, "bodyHz", floatArrayOf(90f, 150f)),
                    metalHz = optFloatArray(it, "metalHz", floatArrayOf(420f, 620f)),
                    bodyGain = it.optDouble("bodyGain", 0.6).toFloat(),
                    metalGain = it.optDouble("metalGain", 0.5).toFloat(),
                    crackGain = it.optDouble("crackGain", 0.8).toFloat(),
                    bodyDecayS = it.optDouble("bodyDecayS", 0.08),
                    metalDecayS = it.optDouble("metalDecayS", 0.025),
                    crackDecayS = it.optDouble("crackDecayS", 0.004),
                )
            }
            val bodyModes = flt?.optJSONArray("bodyModes")?.let { modes ->
                List(modes.length()) { index ->
                    val mode = modes.getJSONObject(index)
                    BodyModeSpec(
                        frequencyHz = mode.optDouble("frequencyHz", 100.0),
                        q = mode.optDouble("q", 1.5),
                        gain = mode.optDouble("gain", 0.1).toFloat(),
                    )
                }
            } ?: emptyList()
            val induction = lay?.optJSONObject("induction")?.let {
                if (!it.optBoolean("enabled", true)) null else InductionSpec(
                    speedRatio = it.optDouble("speedRatio", 1.0),
                    startRpm = it.optDouble("startRpm", 1500.0),
                    orders = optIntArray(it, "orders", intArrayOf()),
                    gains = optFloatArray(it, "gains", floatArrayOf()),
                )
            }
            val mechanical = lay?.optJSONObject("mechanical")?.let {
                MechanicalSpec(
                    orders = optIntArray(it, "orders", intArrayOf()),
                    gains = optFloatArray(it, "gains", floatArrayOf()),
                )
            }
            return VehicleProfile(
                name = o.optString("name", "Vehicle"),
                cylinders = cylinders,
                stroke = stroke,
                firingTiming = firingTiming,
                idleRpm = eng.optDouble("idleRpm", 700.0),
                redlineRpm = eng.optDouble("redlineRpm", 6800.0),
                harmonics = harmonics,
                harmMult = harmMult,
                waveform = syn.optString("waveform", "sawtooth"),
                combJitter = syn.optDouble("combJitter", 0.03).toFloat(),
                exhaustResonance = syn.optDouble("exhaustResonance", 0.97).toFloat(),
                exhaustWindow = syn.optDouble("exhaustWindow", 0.5).toFloat(),
                decayRad = syn.optDouble("decayRad", 0.6).toFloat(),
                turbo = turbo,
                overspeedMuteKmh = map?.optDouble("overspeedMuteKmh", 150.0) ?: 150.0,
                character = o.optString("character", "sport"),
                motorFreqMult = eng.optDouble("motorFreqMult", 0.0),
                driveline = driveline,
                combustionVariation = variation,
                afterfire = afterfire,
                bodyModes = bodyModes,
                induction = induction,
                mechanical = mechanical,
                exhaustGain = syn.optDouble("exhaustGain", 0.70).toFloat(),
                harmonicGain = syn.optDouble("harmonicGain", 0.30).toFloat(),
                raspGain = syn.optDouble("raspGain", 0.0).toFloat(),
                softClipDrive = syn.optDouble("softClipDrive", 2.2).toFloat(),
            )
        }

        private fun optFloatArray(o: JSONObject, key: String, def: FloatArray): FloatArray {
            val a = o.optJSONArray(key) ?: return def
            return FloatArray(a.length()) { a.getDouble(it).toFloat() }
        }

        private fun optIntArray(o: JSONObject, key: String, def: IntArray): IntArray {
            val a = o.optJSONArray(key) ?: return def
            return IntArray(a.length()) { a.getInt(it) }
        }

        private fun optDoubleArray(o: JSONObject, key: String, def: DoubleArray): DoubleArray {
            val a = o.optJSONArray(key) ?: return def
            return DoubleArray(a.length()) { a.getDouble(it) }
        }

        /** 默认等间距点火时序 (rad)。 */
        private fun defaultFiringTiming(cylinders: Int, stroke: Int): DoubleArray {
            val cycle = if (stroke == 4) 4.0 * PI else 2.0 * PI
            return DoubleArray(cylinders) { it * cycle / cylinders }
        }

        /** 内置默认车型 (V8 sport-like)。直接构造, 避免单测触碰 org.json (Android stub)。 */
        val DEFAULT: VehicleProfile by lazy {
            VehicleProfile(
                name = "Crossplane V8",
                cylinders = 8,
                stroke = 4,
                firingTiming = DoubleArray(8) { it * (4.0 * PI / 8.0) },
                idleRpm = 650.0,
                redlineRpm = 6800.0,
                harmonics = floatArrayOf(1.0f, 0.55f, 0.32f, 0.18f, 0.09f),
                harmMult = intArrayOf(1, 2, 3, 4, 5),
                waveform = "sawtooth",
                combJitter = 0.03f,
                exhaustResonance = 0.97f,
                exhaustWindow = 0.5f,
                decayRad = 0.6f,
                turbo = LayerSpec(10.0, 0.12f, 3000.0),
                overspeedMuteKmh = 150.0,
                character = "sport",
            )
        }
    }
}

data class LayerSpec(val freqMult: Double, val gain: Float, val thresholdRpm: Double)

data class DrivelineSpec(
    val gearRatios: DoubleArray,
    val finalDrive: Double,
    val wheelRadiusM: Double,
    val launchRpm: Double,
    val shiftRpm: Double,
    val shiftDurationS: Double,
    val shiftMinGain: Double,
    val upshiftSpeedKmh: DoubleArray = doubleArrayOf(),
    val downshiftSpeedKmh: DoubleArray = doubleArrayOf(),
    val speedCeilingKmh: Double = 144.0,
)

data class CombustionVariationSpec(
    val startRpm: Double,
    val fullRpm: Double,
    val depth: Double,
    val correlation: Double,
    val notchProbability: Double,
    val notchDepth: Double,
    val minimumGain: Double,
    val maximumGain: Double,
    val cylinderGain: FloatArray,
)

data class AfterfireSpec(
    val minimumRpm: Double,
    val throttleDrop: Double,
    val clusterSize: Int,
    val intervalS: Double,
    val bodyHz: FloatArray,
    val metalHz: FloatArray,
    val bodyGain: Float,
    val metalGain: Float,
    val crackGain: Float,
    val bodyDecayS: Double,
    val metalDecayS: Double,
    val crackDecayS: Double,
)

data class BodyModeSpec(val frequencyHz: Double, val q: Double, val gain: Float)

data class InductionSpec(
    val speedRatio: Double,
    val startRpm: Double,
    val orders: IntArray,
    val gains: FloatArray,
)

data class MechanicalSpec(val orders: IntArray, val gains: FloatArray)
