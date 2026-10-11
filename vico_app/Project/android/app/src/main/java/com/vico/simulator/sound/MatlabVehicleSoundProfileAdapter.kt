package com.vico.simulator.sound

import android.content.res.AssetManager
import java.security.MessageDigest

/** Production bridge: profile identity is derived from authoritative bank bytes and loaded spec. */
object MatlabVehicleSoundProfileAdapter {
    fun load(assets: AssetManager, vehicleKey: String): VehicleSoundProfile {
        val bank = MatlabSoundBankLoader.load(assets, vehicleKey)
        val manifestHash = digestManifest(assets, vehicleKey)
        val hashes = mapOf("bank_manifest" to manifestHash)
        return VehicleSoundProfile(
            version = 1,
            vehicleKey = bank.vehicleKey,
            engineFamily = SupportedVehicleProfiles.familyFor(bank.vehicleKey),
            bankIdentity = "matlab:$manifestHash",
            sampleRateHz = bank.sampleRateHz,
            channels = 1,
            artifactHashes = hashes,
            qualificationState = "LOADED_FROM_AUTHORITATIVE_BANK",
            idleRpm = bank.powertrain.idleRpm,
            redlineRpm = bank.powertrain.redlineRpm,
            gearRatios = bank.powertrain.gearRatios.toList(),
            finalDrive = bank.powertrain.finalDrive,
            wheelRadiusM = bank.powertrain.wheelRadiusM,
        ).also { profile -> profile.validate().getOrThrow() }
    }

    private fun digestManifest(assets: AssetManager, vehicleKey: String): String {
        val roots = listOf("s12_v10/$vehicleKey", "matlab_v6/$vehicleKey")
        val bytes = roots.firstNotNullOfOrNull { root ->
            runCatching { assets.open("$root/manifest.json").use { it.readBytes() } }.getOrNull()
        } ?: error("missing manifest for $vehicleKey")
        return MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }
}
