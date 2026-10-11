package com.vico.simulator.sound

import org.junit.Assert.assertFailsWith
import org.junit.Assert.assertTrue
import org.junit.Test

class VehicleSoundProfileLoaderCompatibilityTest {
    @Test
    fun rejectsLegacySyntheticProfileData() {
        assertFailsWith<IllegalArgumentException> {
            VehicleSoundProfile.legacy("c63_w204_v6", "legacy")
        }
    }

    @Test
    fun supportedVehicleKeysRemainExplicit() {
        assertTrue(SupportedVehicleProfiles.keys.contains("c63_w204_v6"))
        assertTrue(SupportedVehicleProfiles.keys.contains("gtr_r35"))
        assertTrue(SupportedVehicleProfiles.keys.contains("lfa"))
    }
}
