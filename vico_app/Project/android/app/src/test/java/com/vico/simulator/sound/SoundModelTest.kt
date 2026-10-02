package com.vico.simulator.sound

import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import java.io.BufferedReader
import java.io.InputStreamReader
import kotlin.math.abs
import kotlin.math.max

/**
 * 对齐 Python 参考轨迹（.stitch-cache/sound-ref/jovi_ev_sound_trace.csv，由
 * E:\Tesla_speed\prj\tools\sound_sim\simulate_sound.py 生成）。PRD AC-06 可追溯。
 */
class SoundModelTest {

    /** 复现 Python build_demo_drive_cycle(duration=12, step=0.02, 600 点)。逐行一致。 */
    private fun buildDemoDriveCycle(): List<DrivePoint> {
        val duration = 12.0
        val step = 0.02
        val steps = (duration / step).toInt().coerceAtLeast(1)
        val points = ArrayList<DrivePoint>(steps)
        var lastSpeedMps = 0.0
        for (i in 0 until steps) {
            val t = i * step
            val throttle: Double
            val accel: Double
            when {
                t < duration * 0.35 -> { throttle = 0.82; accel = 2.7 }
                t < duration * 0.62 -> { throttle = 0.34; accel = 0.2 }
                t < duration * 0.82 -> { throttle = 0.08; accel = -1.6 }
                else -> { throttle = 0.48; accel = 1.1 }
            }
            val speedMps = max(0.0, lastSpeedMps + accel * step)
            val speed = speedMps * 3.6
            val derivedAccel = (speedMps - lastSpeedMps) / step
            lastSpeedMps = speedMps
            points.add(DrivePoint(t, speed, throttle, derivedAccel, brake = derivedAccel < -1.2))
        }
        return points
    }

    private data class RefRow(
        val timeS: Double, val rpm: Double, val freqHz: Double, val amp: Double,
        val bright: Double, val muted: Boolean, val h: DoubleArray,
    )

    private fun loadRefTrace(): List<RefRow> {
        val rows = ArrayList<RefRow>()
        val res = javaClass.classLoader!!.getResourceAsStream("jovi_ev_sound_trace.csv")
            ?: error("missing jovi_ev_sound_trace.csv test resource")
        BufferedReader(InputStreamReader(res)).use { r ->
            for (line in r.readLines().drop(1)) {
                if (line.isBlank()) continue
                val f = line.split(",")
                rows.add(RefRow(
                    f[0].toDouble(), f[1].toDouble(), f[2].toDouble(), f[3].toDouble(),
                    f[4].toDouble(), f[5].toInt() != 0,
                    doubleArrayOf(f[6].toDouble(), f[7].toDouble(), f[8].toDouble(),
                        f[9].toDouble(), f[10].toDouble()),
                ))
            }
        }
        return rows
    }

    @Test
    fun mapPoint_matches_python_reference_trace() {
        val model = SoundModel()
        val points = buildDemoDriveCycle()
        val ref = loadRefTrace()
        assertEquals(ref.size, points.size, "cycle length should match reference")

        var maxRpmErr = 0.0
        var maxFreqErr = 0.0
        var maxAmpErr = 0.0
        var maxBrightErr = 0.0
        var maxHErr = 0.0
        for (i in points.indices) {
            val state = model.mapPoint(points[i], SoundProfile.SPORT)
            val r = ref[i]
            assertEquals(r.muted, state.muted, "muted mismatch at row $i")
            maxRpmErr = max(maxRpmErr, abs(state.rpm - r.rpm))
            maxFreqErr = max(maxFreqErr, abs(state.frequencyHz - r.freqHz))
            maxAmpErr = max(maxAmpErr, abs(state.amplitude - r.amp))
            maxBrightErr = max(maxBrightErr, abs(state.brightness - r.bright))
            for (k in 0 until 5) {
                maxHErr = max(maxHErr, abs(state.harmonics[k] - r.h[k]))
            }
        }
        // 容差对应 CSV 四舍五入精度
        assertTrue(maxRpmErr < 0.02, "max rpm err $maxRpmErr")
        assertTrue(maxFreqErr < 0.02, "max freq err $maxFreqErr")
        assertTrue(maxAmpErr < 5e-4, "max amp err $maxAmpErr")
        assertTrue(maxBrightErr < 5e-4, "max bright err $maxBrightErr")
        assertTrue(maxHErr < 1e-4, "max harmonic err $maxHErr")
        println("SoundModel vs Python trace OK: maxErr rpm=$maxRpmErr freq=$maxFreqErr amp=$maxAmpErr bright=$maxBrightErr h=$maxHErr")
    }

    @Test
    fun renderState_produces_nonzero_pcm_when_audible() {
        val model = SoundModel()
        val state = model.mapPoint(DrivePoint(0.0, 60.0, 0.5, 1.0, false), SoundProfile.SPORT)
        val pcm = model.renderState(state, 441, 44100)
        assertEquals(441, pcm.size)
        assertTrue(pcm.any { it != 0.toShort() }, "pcm should be non-silent for audible state")
    }

    @Test
    fun overspeed_mutes_output() {
        val model = SoundModel()
        val state = model.mapPoint(DrivePoint(0.0, 160.0, 0.5, 0.0, false), SoundProfile.SPORT)
        assertTrue(state.muted, ">=150 km/h should mute")
        assertEquals(0.0, state.amplitude, 1e-9)
        val pcm = model.renderState(state, 100, 44100)
        assertTrue(pcm.all { it == 0.toShort() }, "muted state renders silence")
    }

    @Test
    fun profiles_produce_distinct_harmonics() {
        val model = SoundModel()
        val p = DrivePoint(0.0, 80.0, 0.6, 1.5, false)
        val soft = model.mapPoint(p, SoundProfile.SOFT)
        val sport = model.mapPoint(p, SoundProfile.SPORT)
        val scifi = model.mapPoint(p, SoundProfile.SCIFI)
        // Soft 谐波 <= Sport; Sci-Fi 高谐波更突出
        assertTrue(soft.harmonics[2] <= sport.harmonics[2] + 1e-6, "soft h3 should be <= sport")
        assertTrue(scifi.harmonics[4] >= soft.harmonics[4] - 1e-6, "scifi h5 should be >= soft")
    }
}
