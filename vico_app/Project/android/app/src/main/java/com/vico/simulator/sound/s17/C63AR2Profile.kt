package com.vico.simulator.sound.s17
internal enum class C63AR2Mode { AH,T,S2,E2,SE2 }
internal class C63AR2Profile(val fixedDelay:Int?=null,val arrivalSeed:Long=5900049L) {
    init {require(arrivalSeed!=0L && (fixedDelay==null || fixedDelay in 0..48))}
    val textureScale=9.786453030584157
    val eventSeed=5900017L
    val identity="C63_AR2_FIXED48|$arrivalSeed|$fixedDelay|$textureScale|$eventSeed"
    val sourceDependencies="C63AR2Source,C63BarkArrivalQueue,C63MechanicalTexture@9.786453030584157,C63AR2AfterfireRuntime(seed=5900017,spread=0),C63IdleRuntime,C63ShiftRuntime,FrozenC63Output,h=0.40803954754257843"
}
