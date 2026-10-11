package com.vico.simulator.sound

/**
 * Compatibility adapter between versioned profiles and existing sound-bank
 * selection. It does not replace the current renderer or frozen assets.
 */
class VehicleSoundProfileLoader {
    fun load(vehicleKey: String, bankIdentity: String): VehicleSoundProfile {
        val profile = VehicleSoundProfile.legacy(vehicleKey, bankIdentity)
        profile.validate().getOrThrow()
        return profile
    }
}
