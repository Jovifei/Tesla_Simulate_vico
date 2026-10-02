package com.vico.simulator.sound

/** Whole-session counters; no audio-thread allocation. Quantiles round up to 100us. */
internal class SessionTiming {
    private val bins=LongArray(201)
    var count=0L; private set
    var maxNs=0L; private set
    var deadlineMisses=0L; private set
    fun record(ns:Long) {
        require(ns>=0)
        count++;maxNs=maxOf(maxNs,ns)
        if(ns>=20_000_000)deadlineMisses++
        bins[minOf(200L,(ns+99_999)/100_000).toInt()]++
    }
    fun percentile(percent:Int):Long? {
        require(percent in 1..100)
        if(count==0L)return null
        val target=(count*percent+99)/100
        var seen=0L
        for(i in bins.indices){seen+=bins[i];if(seen>=target)return if(i==200)maxOf(20_000_000L,maxNs) else i*100_000L}
        return maxNs
    }
    fun clear(){bins.fill(0);count=0;maxNs=0;deadlineMisses=0}
}
