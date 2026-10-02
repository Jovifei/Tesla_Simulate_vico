package com.vico.simulator.sound.s16
internal enum class C63AudibleMode { AH,S,E,SE }
/** Development defaults are not a qualified/selected app voice. */
internal class C63AudibleProfile(decays:DoubleArray=doubleArrayOf(.045,.038,.034,.030),val textureScale:Double=1.0,
    val eventSeed:Long=5900017L,val eventSpread:Double=0.0,val referenceBinding:String="DEVELOPMENT_NOT_QUALIFIED") {
    private val tau=decays.copyOf()
    init {
        require(textureScale.isFinite() && textureScale>=0 && eventSeed!=0L && eventSpread.isFinite() && eventSpread>=0 && eventSpread<=.6)
        C63BarkModes(tau) // Validate the only permitted acoustic fitting domain.
    }
    fun decays()=tau.copyOf()
    val identity=referenceBinding+"|"+tau.joinToString{java.lang.Double.toHexString(it)}+"|"+
        java.lang.Double.toHexString(textureScale)+"|"+eventSeed+"|"+java.lang.Double.toHexString(eventSpread)
    companion object {
        /** One frozen fit, not a qualified app default. No post-holdout refitting. */
        fun frozenAR1()=C63AudibleProfile(doubleArrayOf(.012602216564118862,.038,.0085,.03),9.786453030584157,
            5900017L,0.0,"0aee164277afc36691c468ef6778b12d637b4d16b5e7cde5118d7e33359babea")
    }
}
