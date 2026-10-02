package com.vico.simulator.sensor

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

class DemoMotionController(initialSpeedKmh: Double = 0.0) {

    var speedKmh: Double = initialSpeedKmh.coerceAtLeast(0.0)
        private set
    var accelMps2: Double = 0.0
        private set

    private var scenario = "stop"

    fun setScenario(key: String) {
        scenario = key
    }

    fun reset(speedKmh: Double = 0.0) {
        this.speedKmh = speedKmh.coerceAtLeast(0.0)
        accelMps2 = 0.0
    }

    fun step(dtSeconds: Double) {
        val dt = dtSeconds.coerceIn(0.001, 0.1)
        val targetSpeed = when (scenario) {
            "launch" -> 60.0
            "cruise" -> 80.0
            "overspeed" -> 144.0
            "decel", "stop" -> 0.0
            else -> 0.0
        }
        val maxForward = when (scenario) {
            "launch" -> 3.5
            "overspeed" -> 2.5
            else -> 2.0
        }
        val maxBrake = if (scenario == "decel") 4.0 else 3.2
        val speedError = targetSpeed - speedKmh
        var desiredAccel = (speedError * 0.52).coerceIn(-maxBrake, maxForward)
        if (abs(speedError) < 0.18) desiredAccel = 0.0

        val maxJerk = 5.5
        accelMps2 += (desiredAccel - accelMps2).coerceIn(-maxJerk * dt, maxJerk * dt)
        speedKmh = max(0.0, speedKmh + accelMps2 * dt * 3.6)

        if (targetSpeed == 0.0 && speedKmh < 0.2 && abs(accelMps2) < 0.1) {
            speedKmh = 0.0
            accelMps2 = 0.0
        } else if (targetSpeed > 0.0 && abs(speedKmh - targetSpeed) < 0.08 && abs(accelMps2) < 0.05) {
            speedKmh = targetSpeed
            accelMps2 = 0.0
        }
    }
}
