package com.vico.simulator.sound.s17
/** Bark-only impulse arrival; complete area, original event id and bank preserved. */
internal class C63BarkArrivalQueue(private val seed:Long,private val fixedDelay:Int?=null) {
    init {require(seed!=0L && (fixedDelay==null || fixedDelay in 0..48))}
    class Snapshot internal constructor(internal val seed:Long,internal val fixed:Int?,internal val l:DoubleArray,internal val r:DoubleArray,
        internal val cursor:Int,internal val rng:Long,internal val event:Long,internal val values:DoubleArray,
        internal val frame:Long,internal val historyFrames:LongArray,internal val targetFrames:LongArray,internal val delays:IntArray,
        internal val areas:DoubleArray,internal val banks:IntArray)
    private val l=DoubleArray(64);private val r=DoubleArray(64)
    private var cursor=0;private var rng=seed;private var lastEvent=-1L
    var left=0.0;private set
    var right=0.0;private set
    var injectedArea=0.0;private set
    var emittedArea=0.0;private set
    var lastDelay=0;private set
    var rawArrivals=0L;private set
    var distinctImpulseFrames=0L;private set
    private var frame=0L
    private val historyFrame=LongArray(4096);private val targetFrame=LongArray(4096);private val delayHistory=IntArray(4096)
    private val areaHistory=DoubleArray(4096);private val bankHistory=IntArray(4096)
    private fun delay():Int {
        fixedDelay?.let{return it}
        rng=rng xor(rng shl 13);rng=rng xor(rng ushr 7);rng=rng xor(rng shl 17)
        val u=((rng*2685821657736338717L) ushr 11).toDouble()/9007199254740992.0
        return (49*u).toInt()
    }
    fun inject(event:Long,bank:Int,area:Double,sourceFrame:Long=event) {
        require(event>lastEvent && sourceFrame>=0 && bank in 0..1 && area.isFinite() && area>=0)
        lastDelay=delay();val queue=if(bank==0)l else r;queue[(cursor+lastDelay)%64]+=area
        val history=(rawArrivals%historyFrame.size).toInt()
        historyFrame[history]=sourceFrame;targetFrame[history]=sourceFrame+lastDelay
        delayHistory[history]=lastDelay;areaHistory[history]=area;bankHistory[history]=bank
        injectedArea+=area;lastEvent=event;rawArrivals++
    }
    fun step() {
        left=l[cursor];right=r[cursor];l[cursor]=0.0;r[cursor]=0.0
        val impulse=left+right
        emittedArea+=impulse;if(impulse!=0.0)distinctImpulseFrames++
        cursor=(cursor+1)%64;frame++
    }
    fun pendingArea()=l.sum()+r.sum()
    data class ArrivalHistory(val sourceFrames:LongArray,val targetFrames:LongArray,val delays:IntArray,val areas:DoubleArray,val banks:IntArray,val truncated:Boolean)
    fun arrivalHistory():ArrivalHistory {
        val n=minOf(rawArrivals,historyFrame.size.toLong()).toInt();val first=if(rawArrivals>n)(rawArrivals%historyFrame.size).toInt() else 0
        return ArrivalHistory(LongArray(n){historyFrame[(first+it)%historyFrame.size]},LongArray(n){targetFrame[(first+it)%historyFrame.size]},
            IntArray(n){delayHistory[(first+it)%historyFrame.size]},DoubleArray(n){areaHistory[(first+it)%historyFrame.size]},
            IntArray(n){bankHistory[(first+it)%historyFrame.size]},rawArrivals>historyFrame.size)
    }
    fun snapshot()=Snapshot(seed,fixedDelay,l.copyOf(),r.copyOf(),cursor,rng,lastEvent,doubleArrayOf(left,right,injectedArea,emittedArea,lastDelay.toDouble(),rawArrivals.toDouble(),distinctImpulseFrames.toDouble()),
        frame,historyFrame.copyOf(),targetFrame.copyOf(),delayHistory.copyOf(),areaHistory.copyOf(),bankHistory.copyOf())
    fun restore(snapshot:Snapshot) {
        require(snapshot.seed==seed && snapshot.fixed==fixedDelay && snapshot.l.size==64 && snapshot.r.size==64 && snapshot.cursor in 0..63 && snapshot.values.size==7 &&
            snapshot.historyFrames.size==4096 && snapshot.targetFrames.size==4096 && snapshot.delays.size==4096 && snapshot.areas.size==4096 && snapshot.banks.size==4096)
        snapshot.l.copyInto(l);snapshot.r.copyInto(r);cursor=snapshot.cursor;rng=snapshot.rng;lastEvent=snapshot.event
        left=snapshot.values[0];right=snapshot.values[1];injectedArea=snapshot.values[2];emittedArea=snapshot.values[3];lastDelay=snapshot.values[4].toInt()
        rawArrivals=snapshot.values[5].toLong();distinctImpulseFrames=snapshot.values[6].toLong()
        frame=snapshot.frame;snapshot.historyFrames.copyInto(historyFrame);snapshot.targetFrames.copyInto(targetFrame)
        snapshot.delays.copyInto(delayHistory);snapshot.areas.copyInto(areaHistory);snapshot.banks.copyInto(bankHistory)
    }
}
