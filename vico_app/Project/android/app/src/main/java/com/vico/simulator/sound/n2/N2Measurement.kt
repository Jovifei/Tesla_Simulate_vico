package com.vico.simulator.sound.n2

object N2Measurement {
    data class Result(val finite:Boolean,val rms:Double)
    fun measure(pcm:FloatArray):Result {
        var sum=0.0
        for(v in pcm){if(!v.isFinite()) return Result(false,Double.NaN); sum+=v*v}
        return Result(true, if(pcm.isEmpty())0.0 else kotlin.math.sqrt(sum/pcm.size))
    }
}
