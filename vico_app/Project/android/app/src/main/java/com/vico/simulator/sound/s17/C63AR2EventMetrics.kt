package com.vico.simulator.sound.s17
internal object C63AR2EventMetrics {
    data class Counts(val rawArrivals:Long,val distinctImpulses:Long)
    data class MergedImpulses(val rawArrivals:Int,val frames:LongArray,val areas:DoubleArray)
    fun mergeArrivals(frames:LongArray,areas:DoubleArray):MergedImpulses {
        require(frames.size==areas.size && frames.all{it>=0} && frames.indices.drop(1).all{frames[it]>=frames[it-1]} &&
            areas.all{it.isFinite() && it>=0})
        val mergedFrames=ArrayList<Long>();val mergedAreas=ArrayList<Double>()
        for(i in frames.indices) {
            if(mergedFrames.isNotEmpty() && mergedFrames.last()==frames[i])mergedAreas[mergedAreas.lastIndex]+=areas[i]
            else {mergedFrames.add(frames[i]);mergedAreas.add(areas[i])}
        }
        return MergedImpulses(frames.size,mergedFrames.toLongArray(),mergedAreas.toDoubleArray())
    }
    fun isolatedPeak(envelope:DoubleArray,peak:Int,lo:Int,hi:Int):Boolean {
        require(envelope.all{it.isFinite()} && lo>=0 && hi<=envelope.size && lo<=peak && peak<hi)
        if(peak-lo<12 || hi-peak<=25)return false
        val value=envelope[peak];if(value<=0)return false
        return envelope.slice(lo until peak).min()<=value*.5 && envelope.slice(peak+1 until hi).min()<=value*.5
    }
    fun countImpulses(frames:LongArray):Counts {
        require(frames.all{it>=0} && frames.indices.drop(1).all{frames[it]>=frames[it-1]})
        return Counts(frames.size.toLong(),frames.distinct().size.toLong())
    }
}
