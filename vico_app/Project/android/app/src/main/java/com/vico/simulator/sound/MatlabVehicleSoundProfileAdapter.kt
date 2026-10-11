package com.vico.simulator.sound

import android.content.res.AssetManager
import java.security.MessageDigest

/** Production bridge: profile identity is derived from the authoritative bank, never synthetic defaults. */
object MatlabVehicleSoundProfileAdapter {
    fun load(assets: AssetManager, vehicleKey: String): VehicleSoundProfile {
        val bank = MatlabSoundBankLoader.load(assets, vehicleKey)
        val hashes = mapOf(
            "bank" to digestIdentity(bank.vehicleKey + ":" + bank.sampleRateHz + ":" + bank.loops.size),
        )
        return VehicleSoundProfile(
            version = 1,
            vehicleKey = bank.vehicleKey,
            engineFamily = SupportedVehicleProfiles.familyFor(bank.vehicleKey),
            bankIdentity = "matlab:${bank.vehicleKey}",
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

    private fun digestIdentity(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray())
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
