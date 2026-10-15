package com.vico.simulator.sound

import com.vico.simulator.vehicle.CurrentVehicleCatalog
import java.util.Collections

/** Loaded-bank compatibility snapshot. This contract does not grant acoustic qualification. */
class VehicleSoundProfile(
    val version: Int,
    val vehicleKey: String,
    val engineFamily: String,
    val bankIdentity: String,
    val sampleRateHz: Int,
    val channels: Int,
    artifactHashes: Map<String, String>,
    val qualificationState: String,
    powertrain: MatlabPowertrainSpec,
    normalVariantArtifactHashes: Map<String, String> = emptyMap(),
) {
    /** Exact reference manifest/WAV scope, never a claim about overlaid normal WAVs. */
    val referenceArtifactHashes: Map<String, String> = Collections.unmodifiableMap(LinkedHashMap(artifactHashes))
    val artifactHashes: Map<String, String> get() = referenceArtifactHashes
    /** Additional normal-playback artifacts; empty when normal playback uses the reference unchanged. */
    val normalVariantArtifactHashes: Map<String, String> =
        Collections.unmodifiableMap(LinkedHashMap(normalVariantArtifactHashes))
    private val frozenPowertrain = powertrain.copy(gearRatios = powertrain.gearRatios.copyOf())
    // The original spec has mutable arrays. Never expose the snapshot's arrays to a consumer.
    val powertrain: MatlabPowertrainSpec
        get() = frozenPowertrain.copy(gearRatios = frozenPowertrain.gearRatios.copyOf())
    val idleRpm: Double get() = frozenPowertrain.idleRpm
    val redlineRpm: Double get() = frozenPowertrain.redlineRpm
    val gearRatios: List<Double> get() = frozenPowertrain.gearRatios.toList()
    val finalDrive: Double get() = frozenPowertrain.finalDrive
    val wheelRadiusM: Double get() = frozenPowertrain.wheelRadiusM

    fun validate(): Result<Unit> = runCatching {
        require(version == 1) { "Unsupported profile version" }
        require(CurrentVehicleCatalog.isSupported(vehicleKey)) { "Unsupported vehicle" }
        require(engineFamily == SupportedVehicleProfiles.familyFor(vehicleKey)) { "Engine family mismatch" }
        require(bankIdentity.isNotBlank() && bankIdentity == bankIdentity.trim() &&
            bankIdentity !in setOf("unavailable", "not_prepared") && bankIdentity.none { it.isISOControl() }) {
            "Invalid normal bank identity"
        }
        require(bankIdentity == LiveLoopVariantManifest.normalIdentity(vehicleKey)) { "Normal bank identity mismatch" }
        require(sampleRateHz == 48000 || sampleRateHz == 96000) { "Unsupported sample rate" }
        require(channels == 1) { "Expected mono bank" }
        require(qualificationState == "FROZEN_COMPATIBILITY_ONLY") { "Unsupported qualification state" }
        require(artifactHashes.keys.count { it.endsWith("/manifest.json") } == 1 &&
            artifactHashes.keys.any { it.endsWith(".wav") }) { "Missing manifest or WAV artifact identity" }
        require(artifactHashes.keys.all { it.isNotBlank() && !it.startsWith('/') && '\\' !in it &&
            it.split('/').none { part -> part == "." || part == ".." || part.isEmpty() } }) { "Invalid artifact path" }
        val manifestPath = artifactHashes.keys.single { it.endsWith("/manifest.json") }
        val assetRoot = manifestPath.removeSuffix("/manifest.json")
        require(assetRoot in setOf("s12_v10/$vehicleKey", "matlab_v6/$vehicleKey") &&
            artifactHashes.keys.all { it.startsWith("$assetRoot/") }) { "Artifact vehicle/root mismatch" }
        require(artifactHashes.values.all { it.matches(Regex("[0-9a-f]{64}")) }) { "Expected SHA-256" }
        if (bankIdentity == LiveLoopVariantManifest.C63_ID) {
            val root = LiveLoopVariantManifest.C63_ROOT
            require(sampleRateHz == 48000) { "C63 normal variant requires 48 kHz" }
            require(this.normalVariantArtifactHashes.size == 5 &&
                this.normalVariantArtifactHashes["$root/manifest.properties"] == LiveLoopVariantManifest.MANIFEST_SHA256 &&
                this.normalVariantArtifactHashes.keys.count { it.endsWith(".wav") } == 4 &&
                this.normalVariantArtifactHashes.keys.all { it.startsWith("$root/") &&
                    it.split('/').none { part -> part == "." || part == ".." || part.isEmpty() } && '\\' !in it } &&
                this.normalVariantArtifactHashes.values.all { it.matches(Regex("[0-9a-f]{64}")) }) {
                "Missing or invalid normal variant artifact identity"
            }
        } else {
            require(this.normalVariantArtifactHashes.isEmpty()) { "Unexpected variant artifacts for reference playback" }
        }
        val spec = frozenPowertrain
        require(spec.idleRpm.isFinite() && spec.idleRpm > 0 &&
            spec.redlineRpm.isFinite() && spec.redlineRpm > spec.idleRpm) { "Invalid RPM bounds" }
        require(spec.gearRatios.size >= 2 && spec.gearRatios.all { it.isFinite() && it > 0 } &&
            spec.gearRatios.toList().zipWithNext().all { it.first > it.second }) { "Invalid gear ratios" }
        require(spec.finalDrive.isFinite() && spec.finalDrive > 0 &&
            spec.wheelRadiusM.isFinite() && spec.wheelRadiusM > 0) { "Invalid drivetrain geometry" }
        require(listOf(spec.launchRpm, spec.shiftRpm, spec.afterfireMinimumRpm).all {
            it.isFinite() && it in spec.idleRpm..spec.redlineRpm
        }) { "Invalid powertrain RPM thresholds" }
        require(listOf(spec.shiftAttackS, spec.shiftHoldS, spec.shiftRecoveryS, spec.shiftSettleS).all {
            it.isFinite() && it >= 0
        } && spec.totalShiftTimeS.isFinite() && spec.totalShiftTimeS > 0) { "Invalid shift timing" }
        require(spec.minimumShiftIntervalS.isFinite() && spec.minimumShiftIntervalS > 0) { "Invalid shift interval" }
        require(spec.shiftMinTorque.isFinite() && spec.shiftMinTorque in 0.0..1.0) { "Invalid minimum shift torque" }
        require(spec.shiftReengageGain.isFinite() && spec.shiftReengageGain > 0) { "Invalid reengagement gain" }
        require(spec.downshiftRatio.isFinite() && spec.downshiftRatio > 0 && spec.downshiftRatio < 1) {
            "Invalid downshift ratio"
        }
        require(spec.speedCeilingKmh.isFinite() && spec.speedCeilingKmh > 0) { "Invalid speed ceiling" }
    }
}

object SupportedVehicleProfiles {
    val keys: Set<String> get() = CurrentVehicleCatalog.keys.toSet()
    private val families = mapOf(
        "c63_w204_v6" to "v8", "hellcat_v6" to "v8", "ferrari_458" to "v8",
        "gtr_r35" to "v6", "lfa" to "v10", "supra_jza80" to "i6",
    )
    fun familyFor(vehicleKey: String): String = requireNotNull(families[vehicleKey]) { "Unsupported vehicle family" }
}
