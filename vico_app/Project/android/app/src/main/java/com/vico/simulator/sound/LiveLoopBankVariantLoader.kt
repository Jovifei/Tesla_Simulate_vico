package com.vico.simulator.sound

import android.content.res.AssetManager

data class NormalLiveBank(val bank:MatlabSoundBank,val identity:String)

/** Normal playback only. Reference loading never calls this overlay. All disk IO precedes rendering. */
object LiveLoopBankVariantLoader {
    fun loadForNormalPlayback(assets:AssetManager,reference:MatlabSoundBank):NormalLiveBank {
        val identity=LiveLoopVariantManifest.normalIdentity(reference.vehicleKey)
        if(identity==LiveLoopVariantManifest.LEGACY_ID)return NormalLiveBank(reference,identity)
        require(reference.vehicleKey=="c63_w204_v6"&&reference.sampleRateHz==48000)
        val sourceRoot="s12_v10/${reference.vehicleKey}"
        val candidateRoot=LiveLoopVariantManifest.C63_ROOT
        fun read(path:String)=assets.open(path).use{it.readBytes()}
        val validated=LiveLoopVariantManifest.validate(read("$candidateRoot/manifest.properties"),read("$sourceRoot/manifest.json"),
            {read("$sourceRoot/$it")},{read("$candidateRoot/$it")})
        return NormalLiveBank(LiveLoopBankOverlay.apply(reference,validated),validated.variantId)
    }
}
