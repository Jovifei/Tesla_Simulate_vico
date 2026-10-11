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
        require(engineFamily == SupportedVehicleProfiles.familyFor(vehicleKey))
        require(bankIdentity.isNotBlank())
        require(sampleRateHz == 48000 || sampleRateHz == 96000)
        require(channels == 1)
        require(artifactHashes.isNotEmpty())
        require(artifactHashes.keys.all { it.isNotBlank() })
        require(artifactHashes.values.all { it.matches(Regex("[0-9a-fA-F]{16,}")) })
        require(idleRpm.isFinite() && redlineRpm.isFinite() && redlineRpm > idleRpm)
        require(finalDrive.isFinite() && finalDrive > 0)
        require(wheelRadiusM.isFinite() && wheelRadiusM > 0)
        require(gearRatios.size >= 2 && gearRatios.all { it.isFinite() && it > 0 })
        require(gearRatios.zipWithNext().all { it.first > it.second })
    }

    companion object {
        fun legacy(vehicleKey: String, bankIdentity: String): VehicleSoundProfile {
            error("legacy profile requires authoritative MatlabSoundBank")
        }
    }
}

object SupportedVehicleProfiles {
    val keys = setOf("c63_w204_v6", "hellcat_v6", "ferrari_458", "gtr_r35", "lfa", "supra_jza80")

    private val families = mapOf(
        "c63_w204_v6" to "v8",
        "hellcat_v6" to "v8",
        "ferrari_458" to "v8",
        "gtr_r35" to "v6",
        "lfa" to "v10",
        "supra_jza80" to "i6",
    )

    fun familyFor(vehicleKey: String): String = requireNotNull(families[vehicleKey])
}
