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

/**
 * Immutable preregistered N2 response package.
 *
 * The candidate is qualification-only and is not wired into AudioEngine.  Eight actual
 * 4096-frame causal responses replace only the bark stem; a separate 12288-frame response
 * family is used by the event process.
 */
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
    private val bank = Array(responses.size) { responses[it].copyOf() }
    private val weights = coefficients.copyOf()
    private val eventMain = eventResponse.copyOf()
    private val eventA = eventNoiseA.copyOf()
    private val eventB = eventNoiseB.copyOf()

    val identity: String

    init {
        require(bank.size == BASIS_COUNT && weights.size == BASIS_COUNT) { "N2 basis count mismatch" }
        bank.forEach { validateNormalized(it, BASIS_LENGTH, "continuous") }
        for (event in listOf(eventMain, eventA, eventB)) validateNormalized(event, EVENT_LENGTH, "event")
        require(weights.all { it.isFinite() && it >= 0.0 && it <= 1.0 } && weights.any { it > 0.0 }) {
            "N2 coefficient contract mismatch"
        }
        require(sourceScale.isFinite() && sourceScale > 0.0 && sourceScale <= 4.0)
        require(randomFraction.isFinite() && randomFraction in 0.0..0.25)
        require(eventScale.isFinite() && eventScale > 0.0 && eventScale <= 4.0)
        require(eventNoiseFraction.isFinite() && eventNoiseFraction in 0.0..0.5)
        require(sourceSeed != 0L && occurrenceSeed != 0L && responseSeed != 0L)
        require(eventMain.copyOfRange(8192, EVENT_LENGTH).sumOf { it * it } > 1e-8) {
            "N2 event response has no registered late tail"
        }
        identity = computeIdentity()
    }

    fun basis(index: Int): DoubleArray {
        require(index in 0 until BASIS_COUNT)
        return bank[index].copyOf()
    }

    fun coefficients(): DoubleArray = weights.copyOf()
    fun eventResponse(): DoubleArray = eventMain.copyOf()
    fun eventNoiseA(): DoubleArray = eventA.copyOf()
    fun eventNoiseB(): DoubleArray = eventB.copyOf()

    private fun computeIdentity(): String {
        val hash = MessageDigest.getInstance("SHA-256")
        fun putInt(value: Int) {
            hash.update(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value).array())
        }
        fun putLong(value: Long) {
            hash.update(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putLong(value).array())
        }
        fun putDouble(value: Double) {
            hash.update(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putDouble(value).array())
        }
        fun putArray(values: DoubleArray) = values.forEach(::putDouble)

        hash.update(CANDIDATE_ID.toByteArray(Charsets.US_ASCII))
        putInt(SAMPLE_RATE); putInt(BASIS_COUNT); putInt(BASIS_LENGTH); putInt(EVENT_LENGTH)
        putInt(CONTINUOUS_BUDGET); putInt(EVENT_BUDGET)
        putDouble(sourceScale); putDouble(randomFraction); putDouble(eventScale); putDouble(eventNoiseFraction)
        putLong(sourceSeed); putLong(occurrenceSeed); putLong(responseSeed)
        putArray(weights)
        bank.forEach(::putArray)
        putArray(eventMain); putArray(eventA); putArray(eventB)
        return hash.digest().joinToString("") { "%02x".format(it) }
    }

    companion object {
        const val CANDIDATE_ID = "C63_N2_CONTINUOUS_V1"
        const val SAMPLE_RATE = 48000
        const val BASIS_COUNT = 8
        const val BASIS_LENGTH = 4096
        const val EVENT_LENGTH = 12288
        const val CONTINUOUS_BUDGET = 48
        const val EVENT_BUDGET = 24

        private val EDGES = doubleArrayOf(80.0, 140.0, 220.0, 340.0, 520.0, 800.0, 1250.0, 2000.0, 3200.0)
        private val COEFFICIENTS = doubleArrayOf(.52, .46, .39, .33, .27, .22, .17, .12)

        fun bandEdgesHz(): DoubleArray = EDGES.copyOf()

        fun preregistered(): N2Profile {
            val responses = Array(BASIS_COUNT) { i ->
                val center = sqrt(EDGES[i] * EDGES[i + 1])
                val tau = .038 - i * .003
                normalizedFiniteResponse(BASIS_LENGTH, center, tau, i * .17)
            }
            return N2Profile(
                responses = responses,
                coefficients = COEFFICIENTS,
                eventResponse = normalizedFiniteResponse(EVENT_LENGTH, 95.0, .055, .11),
                eventNoiseA = normalizedFiniteResponse(EVENT_LENGTH, 430.0, .045, .37),
                eventNoiseB = normalizedFiniteResponse(EVENT_LENGTH, 1250.0, .030, .73),
            )
        }

        private fun normalizedFiniteResponse(size: Int, hz: Double, tau: Double, phase: Double): DoubleArray {
            require(size > 1 && hz > 0.0 && tau > 0.0)
            val values = DoubleArray(size) { n ->
                exp(-n / (tau * SAMPLE_RATE)) * sin(2.0 * PI * hz * n / SAMPLE_RATE + phase)
            }
            val mean = values.sum() / values.size
            for (i in values.indices) values[i] -= mean
            values[values.lastIndex] -= values.sum()
            val norm = sqrt(values.sumOf { it * it })
            require(norm.isFinite() && norm > 0.0)
            for (i in values.indices) values[i] /= norm
            return values
        }

        private fun validateNormalized(values: DoubleArray, size: Int, label: String) {
            require(values.size == size && values.all { it.isFinite() }) { "Malformed N2 $label response" }
            require(abs(values.sum()) < 1e-8) { "N2 $label response must be zero-DC" }
            require(abs(values.sumOf { it * it } - 1.0) < 1e-6) { "N2 $label response must be L2 normalized" }
        }
    }
}
