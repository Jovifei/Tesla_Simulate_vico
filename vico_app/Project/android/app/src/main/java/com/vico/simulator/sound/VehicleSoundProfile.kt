package com.vico.simulator.sound

/**
 * Versioned vehicle-to-sound contract. This is a compatibility boundary, not a
 * replacement for the existing powertrain or frozen sound assets.
 */
data class VehicleSoundProfile(
    val version: Int,
    val vehicleKey: String,
    val engineFamily: String,
    val bankIdentity: String,
    val sampleRateHz: Int,
    val channels: Int,
    val artifactHashes: Map<String, String>,
    val qualificationState: String,
) {
    fun validate(): Result<Unit> = runCatching {
        require(version == 1) { "unsupported profile version" }
        require(vehicleKey.isNotBlank()) { "vehicle key missing" }
        require(engineFamily.isNotBlank()) { "engine family missing" }
        require(bankIdentity.isNotBlank()) { "bank identity missing" }
        require(sampleRateHz > 0) { "invalid sample rate" }
        require(channels > 0) { "invalid channel count" }
        require(artifactHashes.values.none { it.isBlank() }) { "invalid artifact hash" }
    }

    companion object {
        fun legacy(vehicleKey: String, bankIdentity: String): VehicleSoundProfile =
            VehicleSoundProfile(
                version = 1,
                vehicleKey = vehicleKey,
                engineFamily = "legacy-compatible",
                bankIdentity = bankIdentity,
                sampleRateHz = 48000,
                channels = 1,
                artifactHashes = emptyMap(),
                qualificationState = "FROZEN_COMPATIBILITY_ONLY",
            )
    }
}
