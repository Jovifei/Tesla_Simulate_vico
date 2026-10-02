package com.vico.simulator.sound.n2

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.sin
import kotlin.math.sqrt

internal enum class N2Mode { T, S, E, SE }

internal class N2Profile internal constructor(
    responses: Array<DoubleArray>,
    coefficients: DoubleArray,
    eventResponse: DoubleArray,
    eventNoiseA: DoubleArray,
    eventNoiseB: DoubleArray,
    val sourceScale: Double = 1.0,
    val randomFraction: Double = 0.08,
    val eventScale: Double = 1.0,
    val eventNoiseFraction: Double = 0.20,
    val sourceSeed: Long = 0x4e325f535243L,
    val occurrenceSeed: Long = 5900017L,
    val responseSeed: Long = 0x4e325f525350L,
) {
    private val bank = responses.map { it.copyOf() }.toTypedArray()
    private val weights = coefficients.copyOf()
    private val eventMain = eventResponse.copyOf()
    private val eventA = eventNoiseA.copyOf()
    private val eventB = eventNoiseB.copyOf()
    val identity: String
    init {
        require(bank.size == BASIS_COUNT && weights.size == BASIS_COUNT)
        bank.forEach { validateNormalized(it, BASIS_LENGTH) }
        listOf(eventMain,eventA,eventB).forEach { validateNormalized(it, EVENT_LENGTH) }
        require(sourceScale.isFinite() && sourceScale > 0.0 && sourceScale < 100.0)
        require(eventScale.isFinite() && eventScale > 0.0 && eventScale < 100.0)
        require(randomFraction in 0.0..0.25 && eventNoiseFraction in 0.0..0.5)
        require(sourceSeed != 0L && occurrenceSeed != 0L && responseSeed != 0L)
        identity = hash()
    }
    fun basis(i:Int)=bank[i].copyOf()
    fun coefficients()=weights.copyOf()
    fun eventResponse()=eventMain.copyOf()
    fun eventNoiseA()=eventA.copyOf()
    fun eventNoiseB()=eventB.copyOf()
    fun calibratedCopy(source:Double, event:Double):N2Profile = N2Profile(bank,weights,eventMain,eventA,eventB,source,randomFraction,event,eventNoiseFraction,sourceSeed,occurrenceSeed,responseSeed)
    private fun hash():String { val h=MessageDigest.getInstance("SHA-256"); fun d(x:Double){h.update(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putDouble(x).array())}; h.update(CANDIDATE_ID.toByteArray()); d(sourceScale);d(eventScale);weights.forEach(::d);bank.forEach{it.forEach(::d)};eventMain.forEach(::d);eventA.forEach(::d);eventB.forEach(::d);return h.digest().joinToString(""){"%02x".format(it)} }
    companion object {
        const val CANDIDATE_ID="C63_N2_CONTINUOUS_V1"
        const val SAMPLE_RATE=48000
        const val BASIS_COUNT=8
        const val BASIS_LENGTH=4096
        const val EVENT_LENGTH=12288
        const val CONTINUOUS_BUDGET=48
        const val EVENT_BUDGET=24
        private val EDGES=doubleArrayOf(80.0,140.0,220.0,340.0,520.0,800.0,1250.0,2000.0,3200.0)
        private val COEFFICIENTS=doubleArrayOf(.52,.46,.39,.33,.27,.22,.17,.12)
        fun preregistered()=build(1.0,1.0)
        fun calibrated(source:Double=13.728409855272066,event:Double=18.2039020043)=build(source,event)
        private fun build(source:Double,event:Double)=N2Profile(Array(BASIS_COUNT){i->response(BASIS_LENGTH,sqrt(EDGES[i]*EDGES[i+1]),.038-i*.003,i*.17)},COEFFICIENTS,response(EVENT_LENGTH,95.0,.055,.11),response(EVENT_LENGTH,430.0,.045,.37),response(EVENT_LENGTH,1250.0,.030,.73),source,.08,event,.20)
        private fun response(n:Int,hz:Double,tau:Double,phase:Double):DoubleArray { val a=DoubleArray(n){i->exp(-i/(tau*SAMPLE_RATE))*sin(2*PI*hz*i/SAMPLE_RATE+phase)};val m=a.sum()/n;for(i in a.indices)a[i]-=m;a[n-1]-=a.sum();val l=sqrt(a.sumOf{it*it});for(i in a.indices)a[i]/=l;return a }
        private fun validateNormalized(a:DoubleArray,n:Int){require(a.size==n&&a.all{it.isFinite()}&&abs(a.sum())<1e-8&&abs(a.sumOf{it*it}-1)<1e-6)}
    }
}
