package com.vico.simulator.sound.n2

/** N2 candidate contract. HY1/output layers remain external and frozen. */
data class N2Profile(
    val identity:String="C63_N2_STATEFUL_V2",
    val sampleRate:Int=48000,
    val basisLength:Int=4096,
    val basisCount:Int=8,
    val eventLength:Int=12288,
    val continuousBudget:Int=48,
    val eventBudget:Int=24,
    val seed:Long=0x4E325632L,
    val continuousEnabled:Boolean=false
)

data class N2SoundState(
    val rpm:Double,
    val load:Double,
    val throttle:Double,
    val phase:Double,
    val hot:Boolean,
    val gear:Int
)

data class N2Snapshot(val phase:Double,val occurrenceSeed:Long,val responseSeed:Long)
