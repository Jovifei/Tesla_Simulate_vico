package com.vico.simulator.sound

/** Pure compatibility boundary; decoding and artifact hashing belong to the bank loader. */
object VehicleSoundProfileLoader {
    fun fromLoadedBank(
        bank: MatlabSoundBank,
        normalBankIdentity: String,
        normalVariantArtifactHashes: Map<String, String> = emptyMap(),
    ): VehicleSoundProfile =
        VehicleSoundProfile(
            version = 1,
            vehicleKey = bank.vehicleKey,
            engineFamily = SupportedVehicleProfiles.familyFor(bank.vehicleKey),
            bankIdentity = normalBankIdentity,
            sampleRateHz = bank.sampleRateHz,
            channels = 1,
            artifactHashes = bank.artifactHashes,
            qualificationState = "FROZEN_COMPATIBILITY_ONLY",
            powertrain = bank.powertrain,
            normalVariantArtifactHashes = normalVariantArtifactHashes,
        ).also { it.validate().getOrThrow() }

    fun validateLoaded(bank: MatlabSoundBank, profile: VehicleSoundProfile): Result<Unit> = runCatching {
        profile.validate().getOrThrow()
        require(bank.vehicleKey == profile.vehicleKey) { "Vehicle mismatch" }
        require(bank.sampleRateHz == profile.sampleRateHz) { "Sample rate mismatch" }
        require(bank.artifactHashes == profile.artifactHashes) { "Artifact identity mismatch" }
        val spec = profile.powertrain
        // Data-class equality compares DoubleArray references; compare ratios separately.
        require(spec.gearRatios.contentEquals(bank.powertrain.gearRatios)) { "Gear ratio mismatch" }
        require(spec.copy(gearRatios = bank.powertrain.gearRatios) == bank.powertrain) {
            "Powertrain mismatch"
        }
    }
}
