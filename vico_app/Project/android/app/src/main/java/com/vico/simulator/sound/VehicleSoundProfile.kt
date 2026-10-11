package com.vico.simulator.sound

/** Versioned vehicle-to-sound compatibility contract backed by loaded bank data. */
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
        require(sampleRateHz == 48000 || sampleRateHz == 96000)
        require(channels == 1)
        require(artifactHashes.isNotEmpty())
        require(artifactHashes.values.all { it.isNotBlank() })
        require(idleRpm.isFinite() && redlineRpm.isFinite() && redlineRpm > idleRpm)
        require(finalDrive.isFinite() && finalDrive > 0)
        require(wheelRadiusM.isFinite() && wheelRadiusM > 0)
        require(gearRatios.isNotEmpty() && gearRatios.zipWithNext().all { it.first > it.second })
    }

    companion object {
        fun legacy(vehicleKey: String, bankIdentity: String): VehicleSoundProfile {
            error("legacy profile requires authoritative MatlabSoundBank")
        }
    }
}

object SupportedVehicleProfiles {
    val keys = setOf("c63_w204_v6", "hellcat_v6", "ferrari_458", "gtr_r35", "lfa", "supra_jza80")
    val engineFamilies = setOf("v6", "v8", "v10", "flat6", "i6")
}
