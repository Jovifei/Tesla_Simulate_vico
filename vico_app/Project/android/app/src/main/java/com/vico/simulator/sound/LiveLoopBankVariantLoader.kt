package com.vico.simulator.sound

import android.content.res.AssetManager

data class NormalLiveBank(
    val bank: MatlabSoundBank,
    val identity: String,
    val variantArtifactHashes: Map<String, String> = emptyMap(),
)

/** Normal playback only. Reference loading never calls this overlay. All disk IO precedes rendering. */
object LiveLoopBankVariantLoader {
    fun loadForNormalPlayback(assets: AssetManager, reference: MatlabSoundBank): NormalLiveBank =
        loadForNormalPlayback(reference) { path -> assets.open(path).use { it.readBytes() } }

    /** Same production validation and overlay, with byte IO injectable for JVM fixture verification. */
    internal fun loadForNormalPlayback(reference: MatlabSoundBank, readAsset: (String) -> ByteArray): NormalLiveBank {
        val identity = LiveLoopVariantManifest.normalIdentity(reference.vehicleKey)
        if (identity == LiveLoopVariantManifest.LEGACY_ID) return NormalLiveBank(reference, identity)
        require(reference.vehicleKey == "c63_w204_v6" && reference.sampleRateHz == 48000)
        val sourceRoot = "s12_v10/${reference.vehicleKey}"
        val candidateRoot = LiveLoopVariantManifest.C63_ROOT
        val variantReader = BankArtifactReader(readAsset)
        val validated = LiveLoopVariantManifest.validate(
            variantReader.read("$candidateRoot/manifest.properties"), readAsset("$sourceRoot/manifest.json"),
            { readAsset("$sourceRoot/$it") }, { variantReader.read("$candidateRoot/$it") },
        )
        return NormalLiveBank(LiveLoopBankOverlay.apply(reference, validated), validated.variantId,
            variantReader.hashes())
    }
}
