package com.vico.simulator.sound

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.PI

/** VehicleSoundModel 烟雾测试。MATLAB parity (逐样本比对 MATLAB WAV) 待 Jovi 生成参考 WAV 后补充。 */
class VehicleSoundModelTest {

    private fun advancedV8(
        name: String = "C63",
        redline: Double = 7200.0,
        induction: InductionSpec? = null,
        gearRatios: DoubleArray = doubleArrayOf(4.38, 2.86, 1.92),
        upshiftSpeedKmh: DoubleArray = doubleArrayOf(),
        downshiftSpeedKmh: DoubleArray = doubleArrayOf(),
    ): VehicleProfile = VehicleProfile(
        name = name, cylinders = 8, stroke = 4,
        firingTiming = DoubleArray(8) { it * (4.0 * PI / 8.0) },
        idleRpm = 700.0, redlineRpm = redline,
        harmonics = floatArrayOf(1.0f, 0.58f, 0.34f, 0.20f, 0.10f),
        harmMult = intArrayOf(1, 2, 3, 4, 5),
        waveform = "sawtooth", combJitter = 0.02f, exhaustResonance = 0.96f,
        exhaustWindow = 0.48f, decayRad = 0.55f, turbo = null,
        overspeedMuteKmh = 180.0, character = "sport",
        driveline = DrivelineSpec(
            gearRatios = gearRatios, finalDrive = 2.85,
            wheelRadiusM = 0.335, launchRpm = 2300.0, shiftRpm = redline - 200.0,
            shiftDurationS = 0.14, shiftMinGain = 0.20,
            upshiftSpeedKmh = upshiftSpeedKmh,
            downshiftSpeedKmh = downshiftSpeedKmh,
            speedCeilingKmh = 144.0,
        ),
        combustionVariation = CombustionVariationSpec(
            startRpm = 1400.0, fullRpm = 5200.0, depth = 0.25,
            correlation = 0.32, notchProbability = 0.09, notchDepth = 0.55,
            minimumGain = 0.35, maximumGain = 1.42,
            cylinderGain = floatArrayOf(1.03f, 0.96f, 1.01f, 0.94f, 1.04f, 0.97f, 1.00f, 0.95f),
        ),
        afterfire = AfterfireSpec(
            minimumRpm = 2400.0, throttleDrop = 0.22, clusterSize = 6,
            intervalS = 0.045, bodyHz = floatArrayOf(92f, 146f, 178f),
            metalHz = floatArrayOf(425f, 624f, 882f), bodyGain = 0.58f,
            metalGain = 0.82f, crackGain = 1.20f, bodyDecayS = 0.060,
            metalDecayS = 0.018, crackDecayS = 0.003,
        ),
        bodyModes = listOf(BodyModeSpec(88.0, 1.4, 0.05f), BodyModeSpec(178.0, 2.1, 0.08f)),
        induction = induction,
    )

    private fun v12(): VehicleProfile = VehicleProfile(
        name = "V12", cylinders = 12, stroke = 4,
        firingTiming = DoubleArray(12) { it * (4.0 * PI / 12.0) },
        idleRpm = 700.0, redlineRpm = 8000.0,
        harmonics = floatArrayOf(1.0f, 0.4f, 0.2f, 0.1f, 0.05f),
        harmMult = intArrayOf(1, 2, 3, 4, 5),
        waveform = "sine", combJitter = 0.015f, exhaustResonance = 0.92f,
        exhaustWindow = 0.45f, decayRad = 0.5f, turbo = null, overspeedMuteKmh = 150.0, character = "soft",
    )

    @Test
    fun renders_nonzero_pcm_for_audible_state() {
        val m = VehicleSoundModel(VehicleProfile.DEFAULT)
        val state = m.mapPoint(DrivePoint(0.0, 60.0, 0.5, 1.0, false))
        val pcm = m.renderState(state, 4410, 44100)
        assertEquals(4410, pcm.size)
        assertTrue("PCM should be non-silent", pcm.any { it != 0.toShort() })
    }

    @Test
    fun different_vehicles_produce_different_output() {
        val m8 = VehicleSoundModel(VehicleProfile.DEFAULT)
        val m12 = VehicleSoundModel(v12())
        val point = DrivePoint(0.0, 80.0, 0.6, 1.0, false)
        val pcm8 = m8.renderState(m8.mapPoint(point), 4410, 44100)
        val pcm12 = m12.renderState(m12.mapPoint(point), 4410, 44100)
        assertTrue("V8 vs V12 should differ", pcm8.toList() != pcm12.toList())
    }

    @Test
    fun overspeed_reports_mute_without_zeroing_the_source_amplitude() {
        val m = VehicleSoundModel()
        val state = m.mapPoint(DrivePoint(0.0, 160.0, 0.5, 0.0, false))
        assertTrue(">=150 km/h should mute", state.muted)
        assertTrue("audio engine needs a source signal to fade out", state.amplitude > 0.0)
    }

    @Test
    fun character_modifies_harmonics() {
        val m = VehicleSoundModel(VehicleProfile.DEFAULT)
        val point = DrivePoint(0.0, 60.0, 0.5, 1.0, false)
        m.character = SoundProfile.SPORT
        val sportHarmonics = m.mapPoint(point).harmonics
        m.character = SoundProfile.SOFT
        val softHarmonics = m.mapPoint(point).harmonics
        assertTrue("SOFT h2 <= SPORT h2", softHarmonics[1] <= sportHarmonics[1] + 1e-6f)
    }

    @Test
    fun advanced_vehicle_has_audible_idle_at_standstill() {
        val model = VehicleSoundModel(advancedV8())
        val state = model.mapPoint(DrivePoint(0.0, 0.0, 0.0, 0.0, false))
        assertTrue(state.rpm >= 690.0)
        assertTrue(state.amplitude > 0.0)
        assertTrue(model.renderState(state, 882, 44100).any { it != 0.toShort() })
    }

    @Test
    fun acceleration_crossing_shift_point_cuts_the_main_track() {
        val model = VehicleSoundModel(advancedV8(redline = 6200.0))
        var sawHigherGear = false
        var sawTorqueCut = false
        for (step in 0..180) {
            val time = step * 0.05
            val speed = step * 0.75
            val state = model.mapPoint(DrivePoint(time, speed, 1.0, 3.0, false))
            sawHigherGear = sawHigherGear || state.gear > 1
            sawTorqueCut = sawTorqueCut || state.shiftGain < 0.5
        }
        assertTrue("automatic gearbox should upshift", sawHigherGear)
        assertTrue("upshift should interrupt the main sound", sawTorqueCut)
    }

    @Test
    fun lift_off_at_high_rpm_triggers_afterfire_cluster() {
        val model = VehicleSoundModel(advancedV8())
        model.mapPoint(DrivePoint(0.00, 90.0, 0.85, 2.0, false))
        model.mapPoint(DrivePoint(0.05, 92.0, 0.80, 1.0, false))
        val lift = model.mapPoint(DrivePoint(0.10, 92.0, 0.0, -2.2, true))
        assertTrue("high-rpm throttle lift should request afterfire", lift.afterfireTrigger)
        val pcm = model.renderState(lift, 4410, 44100)
        assertTrue("afterfire render must be audible", pcm.any { kotlin.math.abs(it.toInt()) > 2000 })
    }

    @Test
    fun gradual_phone_acceleration_proxy_still_arms_decel_afterfire() {
        val model = VehicleSoundModel(advancedV8())
        var time = 0.0
        repeat(8) {
            model.mapPoint(DrivePoint(time, 90.0, 0.75, 2.2, false))
            time += 0.05
        }
        var triggered = false
        for (index in 0..16) {
            val accel = 2.0 - index * 0.25
            val throttle = (accel / 3.0).coerceIn(0.0, 1.0)
            val state = model.mapPoint(DrivePoint(time, 90.0, throttle, accel, accel < -1.2))
            triggered = triggered || state.afterfireTrigger
            time += 0.05
        }
        assertTrue("gradual lift followed by braking should trigger afterfire", triggered)
    }

    @Test
    fun hellcat_supercharger_layer_changes_the_rendered_signature() {
        val c63 = VehicleSoundModel(advancedV8(name = "C63"))
        val hellcat = VehicleSoundModel(advancedV8(
            name = "Hellcat",
            redline = 6200.0,
            induction = InductionSpec(
                speedRatio = 2.36, startRpm = 1500.0,
                orders = intArrayOf(3, 6, 9, 12),
                gains = floatArrayOf(0.165f, 0.330f, 0.242f, 0.132f),
            ),
        ))
        val point = DrivePoint(0.0, 100.0, 1.0, 3.0, false)
        val c63Pcm = c63.renderState(c63.mapPoint(point), 4410, 44100)
        val hellcatPcm = hellcat.renderState(hellcat.mapPoint(point), 4410, 44100)
        assertTrue(c63Pcm.toList() != hellcatPcm.toList())
    }

    @Test
    fun c63_uses_explicit_three_gear_speed_table() {
        val model = VehicleSoundModel(advancedV8(
            upshiftSpeedKmh = doubleArrayOf(68.0, 108.0),
            downshiftSpeedKmh = doubleArrayOf(55.0, 88.0),
        ))
        assertEquals(1, model.mapPoint(DrivePoint(0.00, 67.0, 0.8, 1.0)).gear)
        assertEquals(2, model.mapPoint(DrivePoint(0.05, 68.0, 0.8, 1.0)).gear)
        assertEquals(2, model.mapPoint(DrivePoint(0.10, 107.0, 0.8, 1.0)).gear)
        assertEquals(3, model.mapPoint(DrivePoint(0.15, 108.0, 0.8, 1.0)).gear)
        assertEquals(2, model.mapPoint(DrivePoint(0.20, 87.0, 0.0, -1.0)).gear)
        assertEquals(1, model.mapPoint(DrivePoint(0.25, 54.0, 0.0, -1.0)).gear)
    }

    @Test
    fun hellcat_uses_four_gears_before_144_kmh() {
        val model = VehicleSoundModel(advancedV8(
            name = "Hellcat",
            redline = 6200.0,
            gearRatios = doubleArrayOf(4.714, 3.143, 2.106, 1.667),
            upshiftSpeedKmh = doubleArrayOf(56.0, 86.0, 129.0),
            downshiftSpeedKmh = doubleArrayOf(44.0, 68.0, 103.0),
        ))
        assertEquals(1, model.mapPoint(DrivePoint(0.00, 55.0, 1.0, 2.0)).gear)
        assertEquals(2, model.mapPoint(DrivePoint(0.05, 56.0, 1.0, 2.0)).gear)
        assertEquals(3, model.mapPoint(DrivePoint(0.10, 86.0, 1.0, 2.0)).gear)
        assertEquals(4, model.mapPoint(DrivePoint(0.15, 129.0, 1.0, 2.0)).gear)
        assertEquals(4, model.mapPoint(DrivePoint(0.20, 144.0, 1.0, 2.0)).gear)
    }

    @Test
    fun driveline_rpm_is_clamped_at_144_kmh() {
        val profile = advancedV8(
            upshiftSpeedKmh = doubleArrayOf(68.0, 108.0),
            downshiftSpeedKmh = doubleArrayOf(55.0, 88.0),
        )
        val atLimit = VehicleSoundModel(profile).mapPoint(DrivePoint(0.0, 144.0, 1.0, 2.0))
        val aboveLimit = VehicleSoundModel(profile).mapPoint(DrivePoint(0.0, 170.0, 1.0, 2.0))
        assertEquals(atLimit.gear, aboveLimit.gear)
        assertEquals(atLimit.rpm, aboveLimit.rpm, 1e-6)
    }
}
