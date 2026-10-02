package com.vico.simulator.sound

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MatlabPowertrainControllerTest {

    private fun c63Spec() = MatlabPowertrainSpec(
        idleRpm = 700.0,
        redlineRpm = 7200.0,
        gearRatios = doubleArrayOf(4.38, 2.86, 1.92),
        finalDrive = 2.85,
        wheelRadiusM = 0.335,
        launchRpm = 2300.0,
        shiftRpm = 7000.0,
        shiftAttackS = 0.018,
        shiftHoldS = 0.032,
        shiftRecoveryS = 0.075,
        shiftSettleS = 0.055,
        shiftMinTorque = 0.22,
        shiftReengageGain = 1.08,
        minimumShiftIntervalS = 0.35,
        downshiftRatio = 0.68,
        speedCeilingKmh = 144.0,
    )

    @Test
    fun c63_40_to_80_kmh_pull_has_only_one_factory_shift() {
        val controller = MatlabPowertrainController(c63Spec())
        var previousGear = 1
        var shifts = 0
        for (step in 0..200) {
            val speed = 40.0 + 40.0 * step / 200.0
            val state = controller.update(step * 0.05, speed, 1.2, 0.55)
            if (state.gear != previousGear) shifts++
            previousGear = state.gear
        }
        assertEquals(1, shifts)
        assertEquals(2, previousGear)
    }

    @Test
    fun shift_speed_is_derived_from_matlab_driveline_data() {
        val speed = c63Spec().upshiftSpeedKmh[0]
        assertEquals(70.8198, speed, 0.01)
    }

    @Test
    fun shift_torque_envelope_has_cut_and_recovery() {
        val controller = MatlabPowertrainController(c63Spec())
        controller.update(0.0, 70.0, 1.0, 0.7)
        val shift = controller.update(0.05, 71.0, 1.0, 0.7)
        val cut = controller.update(0.08, 72.0, 1.0, 0.7)
        val recovered = controller.update(0.30, 75.0, 1.0, 0.7)
        assertEquals(2, shift.gear)
        assertTrue(shift.shiftTrigger)
        assertTrue(!cut.shiftTrigger)
        assertTrue(cut.torqueGain < 0.5)
        assertEquals(1.0, recovered.torqueGain, 0.02)
    }

    @Test
    fun gradual_phone_throttle_proxy_still_releases_matlab_afterfire_clip() {
        val controller = MatlabPowertrainController(c63Spec())
        var time = 0.0
        repeat(8) {
            controller.update(time, 90.0, 2.0, 0.70)
            time += 0.05
        }
        var triggered = false
        for (index in 0..16) {
            val accel = 2.0 - index * 0.25
            val state = controller.update(time, 90.0, accel, (accel / 3.0).coerceIn(0.0, 1.0))
            triggered = triggered || state.afterfireTrigger
            time += 0.05
        }
        assertTrue(triggered)
    }
}
