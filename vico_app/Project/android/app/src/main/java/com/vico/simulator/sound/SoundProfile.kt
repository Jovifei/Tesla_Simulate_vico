package com.vico.simulator.sound

/**
 * Soft / Sport / Sci-Fi 声浪档案预设。
 *
 * Sport = Python `sound_model.py` 默认值（idle 800 / max 6800 / 谐波全开 / 亮度 1.0），
 * [SoundModel.mapPoint] 在 Sport 档下与 Python 参考轨迹逐行一致（AC-06 可追溯）。
 * Soft / Sci-Fi 通过 idle/max、谐波形状权重、亮度缩放区分音色。
 */
enum class SoundProfile(
    val idleRpm: Double,
    val maxRpm: Double,
    val harmonicWeights: FloatArray,
    val brightScale: Float,
    val label: String,
    val color: String,
) {
    SOFT(
        idleRpm = 600.0,
        maxRpm = 5500.0,
        harmonicWeights = floatArrayOf(1.0f, 0.50f, 0.30f, 0.15f, 0.08f),
        brightScale = 0.70f,
        label = "柔和",
        color = "#ff8a3d",
    ),
    SPORT(
        idleRpm = 800.0,
        maxRpm = 6800.0,
        harmonicWeights = floatArrayOf(1.0f, 1.0f, 1.0f, 1.0f, 1.0f),
        brightScale = 1.0f,
        label = "运动",
        color = "#ff3b3b",
    ),
    SCIFI(
        idleRpm = 500.0,
        maxRpm = 8000.0,
        harmonicWeights = floatArrayOf(1.0f, 0.80f, 1.20f, 1.00f, 1.50f),
        brightScale = 0.85f,
        label = "科幻",
        color = "#6ea8ff",
    );

    companion object {
        val DEFAULT: SoundProfile = SPORT

        fun fromKey(key: String?): SoundProfile = when (key?.lowercase()) {
            "soft" -> SOFT
            "scifi", "sci-fi", "sci", "科幻" -> SCIFI
            "sport", "运动" -> SPORT
            else -> SPORT
        }
    }
}
