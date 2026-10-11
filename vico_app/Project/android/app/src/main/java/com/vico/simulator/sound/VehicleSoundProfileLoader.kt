package com.vico.simulator.sound

import com.vico.simulator.vehicle.CurrentVehicleCatalog

/** Compatibility adapter over authoritative loaded banks. */
class VehicleSoundProfileLoader {
    fun load(bank: MatlabSoundBank, normalBankIdentity: String): VehicleSoundProfile {
        require(CurrentVehicleCatalog.isSupported(bank.vehicleKey))
        val spec = bank.powertrain
        return VehicleSoundProfile(
            version = 1,
            vehicleKey = bank.vehicleKey,
            engineFamily = inferEngineFamily(bank.vehicleKey),
            bankIdentity = normalBankIdentity,
            sampleRateHz = bank.sampleRateHz,
            channels = 1,
            artifactHashes = mapOf("manifest" to "${bank.vehicleKey}:${bank.sampleRateHz}"),
            qualificationState = "FROZEN_COMPATIBILITY_ONLY",
            idleRpm = spec.idleRpm,
            redlineRpm = spec.redlineRpm,
            gearRatios = spec.gearRatios.toList(),
            finalDrive = spec.finalDrive,
            wheelRadiusM = spec.wheelRadiusM,
        ).also { it.validate().getOrThrow() }
    }

    fun validateLoaded(bank: MatlabSoundBank, profile: VehicleSoundProfile): Result<Unit> = runCatching {
        require(CurrentVehicleCatalog.isSupported(bank.vehicleKey))
        require(bank.vehicleKey == profile.vehicleKey)
        require(bank.sampleRateHz == profile.sampleRateHz)
        require(profile.channels == 1)
        require(profile.idleRpm == bank.powertrain.idleRpm)
        require(profile.redlineRpm == bank.powertrain.redlineRpm)
    }

    private fun inferEngineFamily(vehicleKey: String): String = when (vehicleKey) {
        "c63_w204_v6", "hellcat_v6" -> "v8"
        "ferrari_458" -> "v8"
        "gtr_r35", "supra_jza80" -> "i6"
        "lfa" -> "v10"
        else -> error("unsupported vehicle family")
    }
}
