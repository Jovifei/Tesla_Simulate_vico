package com.vico.simulator.sensor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DemoMotionControllerTest {

    @Test
    fun stop_scenario_brakes_to_zero_instead_of_holding_the_previous_speed() {
        val demo = DemoMotionController(initialSpeedKmh = 80.0)
        demo.setScenario("stop")

        repeat(450) { demo.step(0.02) }

        assertEquals("remaining speed=${demo.speedKmh}, accel=${demo.accelMps2}", 0.0, demo.speedKmh, 0.1)
        assertTrue("stop must end with no residual acceleration", kotlin.math.abs(demo.accelMps2) < 0.05)
    }

    @Test
    fun launch_settles_at_its_target_without_runaway_speed() {
        val demo = DemoMotionController()
        demo.setScenario("launch")

        repeat(600) { demo.step(0.02) }

        assertEquals(60.0, demo.speedKmh, 1.0)
    }

    @Test
    fun max_speed_scenario_stops_at_144_kmh() {
        val demo = DemoMotionController()
        demo.setScenario("overspeed")

        repeat(1800) { demo.step(0.02) }

        assertEquals(144.0, demo.speedKmh, 0.2)
    }
}
