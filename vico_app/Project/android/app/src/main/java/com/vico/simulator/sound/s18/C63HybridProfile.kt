package com.vico.simulator.sound.s18
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.abs

internal enum class C63HybridMode { T,S,E,SE }
/** Immutable generated DSP parameters. Binary identity includes kernels, seeds and reference constraints. */
internal class C63HybridProfile(periodic:DoubleArray,pressure:DoubleArray,noiseA:DoubleArray,noiseB:DoubleArray,
    val periodicScale:Double,val eventScale:Double,val randomFraction:Double,val eventNoiseFraction:Double,
    weights:DoubleArray,val referenceHash:String,val sourceSeed:Long=5900067L,val eventSeed:Long=5900017L,val responseSeed:Long=5900023L) {
    private val p=periodic.copyOf();private val e=pressure.copyOf();private val a=noiseA.copyOf();private val b=noiseB.copyOf();private val w=weights.copyOf()
    val periodicKernel get()=p.copyOf()
    val afterfirePressure get()=e.copyOf()
    val afterfireNoiseA get()=a.copyOf()
    val afterfireNoiseB get()=b.copyOf()
    val noiseWeights get()=w.copyOf()
    init {
        fun kernel(x:DoubleArray,size:Int){require(x.size==size && x.all{it.isFinite()} && abs(x.sum())<1e-8 &&
            abs(x.sumOf{it*it}-1)<1e-6 && x.last()==0.0){"Malformed HY1 finite response"}}
        kernel(p,2048);for(x in listOf(e,a,b))kernel(x,12288)
        for((x,y) in listOf(e to a,e to b,a to b))require(abs(x.indices.sumOf{x[it]*y[it]})<1e-6){"HY1 event bases must be orthogonal"}
        require(periodicScale.isFinite() && periodicScale>0 && periodicScale<=1000 && eventScale.isFinite() && eventScale>0 && eventScale<=1000)
        require(randomFraction.isFinite() && randomFraction in 0.0..0.25 && eventNoiseFraction.isFinite() && eventNoiseFraction in 0.0..0.5)
        require(w.size==4 && w.all{it.isFinite() && it>=0} && abs(w.sumOf{it*it}-1)<1e-8)
        require(referenceHash.matches(Regex("[0-9a-f]{64}")) && sourceSeed!=0L && eventSeed!=0L && responseSeed!=0L)
    }
    val identity=MessageDigest.getInstance("SHA-256").digest(toBytes()).joinToString(""){"%02x".format(it)}
    fun toBytes():ByteArray {
        val out=ByteBuffer.allocate(BYTES).order(ByteOrder.LITTLE_ENDIAN)
        out.put("C63HY1V1".toByteArray(Charsets.US_ASCII)).putInt(2048).putInt(12288)
        for(v in doubleArrayOf(periodicScale,eventScale,randomFraction,eventNoiseFraction))out.putDouble(v)
        w.forEach{out.putDouble(it)};out.putLong(sourceSeed).putLong(eventSeed).putLong(responseSeed)
        out.put(referenceHash.chunked(2).map{it.toInt(16).toByte()}.toByteArray())
        for(x in listOf(p,e,a,b))x.forEach{out.putDouble(it)}
        check(!out.hasRemaining());return out.array()
    }
    companion object {
        private const val BYTES=311432
        fun fromBytes(bytes:ByteArray):C63HybridProfile {
            require(bytes.size==BYTES){"HY1 binary size mismatch"}
            val input=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);val magic=ByteArray(8);input.get(magic)
            require(magic.toString(Charsets.US_ASCII)=="C63HY1V1" && input.int==2048 && input.int==12288){"HY1 binary format mismatch"}
            val scalars=DoubleArray(4){input.double};val weights=DoubleArray(4){input.double};val seeds=LongArray(3){input.long}
            val ref=ByteArray(32);input.get(ref)
            val p=DoubleArray(2048){input.double};val e=DoubleArray(12288){input.double};val a=DoubleArray(12288){input.double};val b=DoubleArray(12288){input.double}
            return C63HybridProfile(p,e,a,b,scalars[0],scalars[1],scalars[2],scalars[3],weights,
                ref.joinToString(""){"%02x".format(it)},seeds[0],seeds[1],seeds[2])
        }
    }
}
