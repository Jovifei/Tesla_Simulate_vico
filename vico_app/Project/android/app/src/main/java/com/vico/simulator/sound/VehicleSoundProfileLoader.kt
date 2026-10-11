package com.vico.simulator.sound

import com.vico.simulator.vehicle.CurrentVehicleCatalog

/**
 * Compatibility adapter over authoritative loaded banks. It never invents
 * powertrain numbers; MatlabSoundBankLoader owns MatlabPowertrainSpec.
 */
class VehicleSoundProfileLoader {
    fun load(bank: MatlabSoundBank, normalBankIdentity: String): VehicleSoundProfile {
        require(CurrentVehicleCatalog.isSupported(bank.vehicleKey))
        return VehicleSoundProfile(
            version = 1,
            vehicleKey = bank.vehicleKey,
            engineFamily = "matlab-powertrain-spec",
            bankIdentity = normalBankIdentity,
            sampleRateHz = bank.sampleRateHz,
            channels = 1,
            artifactHashes = mapOf("manifest" to "bank/${bank.vehicleKey}"),
            qualificationState = "FROZEN_COMPATIBILITY_ONLY",
        ).also { it.validate().getOrThrow() }
    }

    fun validateLoaded(bank: MatlabSoundBank, profile: VehicleSoundProfile): Result<Unit> = runCatching {
        require(CurrentVehicleCatalog.isSupported(bank.vehicleKey))
        require(bank.vehicleKey == profile.vehicleKey)
        require(bank.sampleRateHz == profile.sampleRateHz)
        require(profile.channels == 1)
        require(profile.engineFamily == "matlab-powertrain-spec")
    }
}
