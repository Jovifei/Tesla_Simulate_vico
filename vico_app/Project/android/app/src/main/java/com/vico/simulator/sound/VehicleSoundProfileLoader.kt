package com.vico.simulator.sound

import com.vico.simulator.vehicle.CurrentVehicleCatalog
import java.security.MessageDigest

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
            artifactHashes = mapOf("bank_manifest" to manifestIdentity(bank)),
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
        require(profile.artifactHashes.values.all { it.matches(Regex("[0-9a-f]{64}")) })
        require(profile.idleRpm == bank.powertrain.idleRpm)
        require(profile.redlineRpm == bank.powertrain.redlineRpm)
        require(profile.finalDrive == bank.powertrain.finalDrive)
        require(profile.wheelRadiusM == bank.powertrain.wheelRadiusM)
    }

    private fun manifestIdentity(bank: MatlabSoundBank): String {
        val data = (bank.vehicleKey + bank.sampleRateHz + bank.powertrain.gearRatios.joinToString(",") +
            bank.powertrain.finalDrive + bank.powertrain.wheelRadiusM).toByteArray()
        return MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) }
    }

    private fun inferEngineFamily(vehicleKey: String): String = when (vehicleKey) {
        "c63_w204_v6", "hellcat_v6", "ferrari_458" -> "v8"
        "gtr_r35" -> "v6"
        "supra_jza80" -> "i6"
        "lfa" -> "v10"
        else -> error("unsupported vehicle family")
    }
}
