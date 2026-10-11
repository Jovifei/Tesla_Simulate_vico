package com.vico.simulator.sound

import com.vico.simulator.vehicle.CurrentVehicleCatalog
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Contract tests for the profile boundary. These tests intentionally use the
 * same loaded-bank shape as production; they do not invent powertrain values.
 */
class VehicleSoundProfileConsumerRegressionTest {
    @Test
    fun supportedVehicleKeysRemainExplicit() {
        assertEquals(
            setOf("c63_w204_v6", "hellcat_v6", "ferrari_458", "gtr_r35", "lfa", "supra_jza80"),
            CurrentVehicleCatalog.keys.toSet(),
        )
    }

    @Test
    fun malformedProfileRejectsNegativeGearAndMissingIdentity() {
        val profile = VehicleSoundProfile(
            1,
            "gtr_r35",
            "v6",
            "normal",
            48000,
            1,
            mapOf("manifest" to ""),
            "FROZEN_COMPATIBILITY_ONLY",
            700.0,
            7000.0,
            listOf(-1.0),
            3.5,
            0.33,
        )
        assertTrue(profile.validate().isFailure)
    }
}
