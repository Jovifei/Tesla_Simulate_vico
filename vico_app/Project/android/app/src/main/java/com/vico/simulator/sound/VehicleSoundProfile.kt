package com.vico.simulator.sound

/** Versioned vehicle-to-sound compatibility contract. */
data class VehicleSoundProfile(
    val version: Int,
    val vehicleKey: String,
    val engineFamily: String,
    val bankIdentity: String,
    val sampleRateHz: Int,
    val channels: Int,
    val artifactHashes: Map<String, String>,
    val qualificationState: String,
    val idleRpm: Double,
    val redlineRpm: Double,
    val gearRatios: List<Double>,
    val finalDrive: Double,
    val wheelRadiusM: Double,
) {
    fun validate(): Result<Unit> = runCatching {
        require(version == 1)
        require(vehicleKey in SupportedVehicleProfiles.keys)
        require(engineFamily in SupportedVehicleProfiles.engineFamilies)
        require(bankIdentity.isNotBlank())
        require(sampleRateHz == 48000)
        require(channels == 1)
        require(artifactHashes.isNotEmpty())
        require(artifactHashes.values.all { it.matches(Regex("[0-9a-fA-F]{16,}")) })
        require(idleRpm.isFinite() && redlineRpm.isFinite() && redlineRpm > idleRpm)
        require(finalDrive.isFinite() && finalDrive > 0)
        require(wheelRadiusM.isFinite() && wheelRadiusM > 0)
        require(gearRatios.isNotEmpty() && gearRatios.zipWithNext().all { it.first > it.second })
    }

    companion object {
        fun legacy(vehicleKey: String, bankIdentity: String): VehicleSoundProfile =
            SupportedVehicleProfiles.requireLegacy(vehicleKey, bankIdentity)
    }
}

object SupportedVehicleProfiles {
    val keys = setOf("c63_w204_v6", "hellcat_v6", "ferrari_458", "gtr_r35", "lfa", "supra_jza80")
    val engineFamilies = setOf("v6", "v8", "v10", "flat6", "i6")

    fun requireLegacy(vehicleKey: String, bankIdentity: String): VehicleSoundProfile {
        require(vehicleKey in keys)
        return VehicleSoundProfile(1, vehicleKey, "legacy-compatible", bankIdentity, 48000, 1,
            mapOf("bank" to "legacy-bound"), "FROZEN_COMPATIBILITY_ONLY",
            700.0, 7000.0, listOf(3.0, 2.0, 1.4, 1.0), 3.5, 0.33)
    }
}
