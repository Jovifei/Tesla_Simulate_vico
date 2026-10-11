package com.vico.simulator.sound

/** Immutable overlay: original bank objects and arrays remain the reference. */
object LiveLoopBankOverlay {
    fun apply(reference:MatlabSoundBank,variant:ValidatedLiveLoopVariant):MatlabSoundBank {
        require(reference.vehicleKey==variant.vehicleKey&&reference.sampleRateHz==48000)
        require(variant.variantId==LiveLoopVariantManifest.C63_ID)
        val replacement=variant.replacements.associateBy{it.rpm to it.load}
        require(replacement.size==4&&variant.replacements.size==4)
        require(replacement.keys==setOf(700.0 to .32,700.0 to .92,1400.0 to .32,1400.0 to .92))
        require(reference.loops.map{it.rpm to it.load}.toSet().size==reference.loops.size)
        require(reference.loops.count{replacement.containsKey(it.rpm to it.load)}==4)
        val loops=reference.loops.map{old->replacement[old.rpm to old.load]?.let{MatlabLoop(old.rpm,old.load,it.audio.samples)} ?: old}
        return reference.copy(loops=loops)
    }
}
