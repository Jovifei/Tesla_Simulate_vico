package com.vico.simulator.sound.s18
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.abs

/** Finite signed response. Original event amplitude and bank are input identities, not output area. */
internal class C63FiniteResponseSource(response:DoubleArray,firstNoise:DoubleArray?=null,secondNoise:DoubleArray?=null) {
    private val kernel=response.copyOf()
    private val noiseA=firstNoise?.copyOf();private val noiseB=secondNoise?.copyOf()
    init {
        require(kernel.size in 1..12288 && kernel.all{it.isFinite()} && kernel.sumOf{it*it}.let{it.isFinite() && it>0})
        require((noiseA==null)==(noiseB==null))
        for(basis in listOfNotNull(noiseA,noiseB))require(basis.size==kernel.size && basis.all{it.isFinite()})
    }
    private val capacity=Integer.highestOneBit(kernel.size-1).let{if(it==0)1 else it shl 1}
    private val mask=capacity-1
    private val l=DoubleArray(capacity);private val r=DoubleArray(capacity)
    private val identity=MessageDigest.getInstance("SHA-256").let{hash->
        for(values in listOfNotNull(kernel,noiseA,noiseB)){
            val bytes=ByteBuffer.allocate(values.size*8).order(ByteOrder.LITTLE_ENDIAN)
            values.forEach{bytes.putDouble(it)};hash.update(bytes.array())
        }
        hash.digest().joinToString(""){"%02x".format(it)}
    }
    private var cursor=0;private var lastEvent=-1L;private var frames=0L
    var events=0L;private set
    var pendingFrames=0;private set
    var left=0.0;private set
    var right=0.0;private set
    fun inject(event:Long,bank:Int,amplitude:Double,w1:Double=0.0,w2:Double=0.0) {
        require(event>=0 && event>lastEvent && bank in 0..1 && amplitude.isFinite() && amplitude in 0.0..2.0)
        require(w1.isFinite() && w2.isFinite() && abs(w1)<=1 && abs(w2)<=1 && (noiseA!=null || w1==0.0 && w2==0.0))
        val target=if(bank==0)l else r
        fun value(i:Int)=amplitude*(kernel[i]+w1*(noiseA?.get(i) ?: 0.0)+w2*(noiseB?.get(i) ?: 0.0))
        for(i in kernel.indices)check((target[(cursor+i) and mask]+value(i)).isFinite()){"Finite response queue overflow"}
        for(i in kernel.indices)target[(cursor+i) and mask]+=value(i)
        lastEvent=event;events++;pendingFrames=maxOf(pendingFrames,kernel.size)
    }
    fun step() {
        left=l[cursor];right=r[cursor];l[cursor]=0.0;r[cursor]=0.0
        cursor=(cursor+1) and mask;frames++;if(pendingFrames>0)pendingFrames--
    }
    fun pendingEnergy()=l.sumOf{it*it}+r.sumOf{it*it}
    class Snapshot internal constructor(internal val identity:String,internal val l:DoubleArray,internal val r:DoubleArray,
        internal val cursor:Int,internal val lastEvent:Long,internal val frames:Long,internal val events:Long,
        internal val pending:Int,internal val left:Double,internal val right:Double)
    fun snapshot()=Snapshot(identity,l.copyOf(),r.copyOf(),cursor,lastEvent,frames,events,pendingFrames,left,right)
    fun restore(s:Snapshot) {
        require(s.identity==identity && s.l.size==capacity && s.r.size==capacity && s.cursor in 0 until capacity &&
            s.pending in 0..kernel.size && s.frames>=0 && s.events>=0 && s.l.all{it.isFinite()} && s.r.all{it.isFinite()} && s.left.isFinite() && s.right.isFinite())
        s.l.copyInto(l);s.r.copyInto(r);cursor=s.cursor;lastEvent=s.lastEvent;frames=s.frames;events=s.events;pendingFrames=s.pending;left=s.left;right=s.right
    }
}
