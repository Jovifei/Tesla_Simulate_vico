package com.vico.simulator.logging

import java.util.concurrent.atomic.AtomicLongArray

/** One audio writer, one non-audio collector. Fixed primitive storage, no writer allocation or IO. */
class AudioDiagnosticRing(private val capacity: Int = 64) {
    init { require(capacity in 2..1024) }
    private val stamps = AtomicLongArray(capacity)
    private val words = AtomicLongArray(capacity * 17)
    @Volatile private var published = 0L
    private var next = 0L
    private var consumed = 0L
    data class Record(val blockId: Long, val frameId: Long, val epoch: Long, val elapsedNs: Long,
        val sampleRate: Int, val bufferFrames: Int, val underruns: Int, val renderNs: Long,
        val writeNs: Long, val writtenFrames: Long, val clipCount: Long, val peak: Double,
        val routeCode: Int, val eventMask: Int, val causeCode: Int, val eventSourceId: Long,
        val blocksInWindow: Long)
    data class Batch(val records: List<Record>, val dropped: Long)
    fun publish(blockId: Long, frameId: Long, epoch: Long, elapsedNs: Long, sampleRate: Int,
                bufferFrames: Int, underruns: Int, renderNs: Long, writeNs: Long, writtenFrames: Long,
                clipCount: Long, peak: Double, routeCode: Int, eventMask: Int, causeCode: Int,
                eventSourceId: Long, blocksInWindow: Long) {
        val sequence=++next
        val slot=((sequence-1)%capacity).toInt();val offset=slot*17
        stamps.set(slot,-sequence)
        words.set(offset,blockId);words.set(offset+1,frameId);words.set(offset+2,epoch);words.set(offset+3,elapsedNs)
        words.set(offset+4,sampleRate.toLong());words.set(offset+5,bufferFrames.toLong());words.set(offset+6,underruns.toLong())
        words.set(offset+7,renderNs);words.set(offset+8,writeNs);words.set(offset+9,writtenFrames);words.set(offset+10,clipCount)
        words.set(offset+11,java.lang.Double.doubleToRawLongBits(peak));words.set(offset+12,routeCode.toLong())
        words.set(offset+13,eventMask.toLong());words.set(offset+14,causeCode.toLong());words.set(offset+15,eventSourceId)
        words.set(offset+16,blocksInWindow)
        stamps.set(slot,sequence);published=sequence
    }
    /** Collector only. Overwrite/concurrent publication gaps are explicit, never an unbounded queue. */
    fun drain(): Batch {
        val end=published
        val start=maxOf(consumed+1,end-capacity+1)
        var dropped=maxOf(0,start-consumed-1)
        val result=ArrayList<Record>(capacity)
        for(sequence in start..end){
            val slot=((sequence-1)%capacity).toInt();val o=slot*17
            if(stamps.get(slot)!=sequence){dropped++;continue}
            val r=Record(words.get(o),words.get(o+1),words.get(o+2),words.get(o+3),
                words.get(o+4).toInt(),words.get(o+5).toInt(),words.get(o+6).toInt(),words.get(o+7),words.get(o+8),
                words.get(o+9),words.get(o+10),java.lang.Double.longBitsToDouble(words.get(o+11)),
                words.get(o+12).toInt(),words.get(o+13).toInt(),words.get(o+14).toInt(),words.get(o+15),words.get(o+16))
            if(stamps.get(slot)==sequence)result.add(r) else dropped++
        }
        consumed=end
        return Batch(result,dropped)
    }
}
