package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class NormalEnvelopeDamperTest {
    private val sampleRate = 48000
    private val modulationHz = 1.8055555555555556
    private fun sample(index: Int, depth: Double = .05): Float {
        val time = index.toDouble() / sampleRate
        return (.2 * (1 + depth * sin(2 * PI * modulationHz * time)) * sin(2 * PI * 700 * time)).toFloat()
    }

    @Test fun warmupTracksWithoutChangingSamples() {
        val dsp = NormalEnvelopeDamper(sampleRate)
        repeat(sampleRate / 4) { index ->
            val x = sample(index)
            assertEquals(x.toRawBits(), dsp.process(x).toRawBits())
        }
        assertEquals(NormalEnvelopeSnapshot(12000, 1.0, 1.0), dsp.snapshot())
    }

    @Test fun zerosAndSubFloorInputRemainUnchanged() {
        for (value in floatArrayOf(0f, 1e-8f, -1e-8f)) {
            val dsp = NormalEnvelopeDamper(sampleRate)
            repeat(sampleRate * 2) { assertEquals(value.toRawBits(), dsp.process(value).toRawBits()) }
            assertEquals(1.0, dsp.snapshot().minGain, 0.0)
            assertEquals(1.0, dsp.snapshot().maxGain, 0.0)
        }
    }

    @Test fun rejectsNonFiniteInputBeforeMutatingState() {
        val a = NormalEnvelopeDamper(sampleRate)
        val b = NormalEnvelopeDamper(sampleRate)
        repeat(20000) { a.process(sample(it)); b.process(sample(it)) }
        for (bad in floatArrayOf(Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY)) {
            val before = a.snapshot()
            try { a.process(bad); fail("Expected IllegalArgumentException") }
            catch (expected: IllegalArgumentException) { assertEquals(before, a.snapshot()) }
        }
        repeat(2000) { assertEquals(b.process(sample(it)).toRawBits(), a.process(sample(it)).toRawBits()) }
    }

    @Test fun boundedDynamicGainKeepsEveryDrySampleWithinThreePercent() {
        val dsp = NormalEnvelopeDamper(sampleRate)
        repeat(sampleRate * 3) { index ->
            val x = sample(index, .7)
            val y = dsp.process(x)
            assertTrue(y.isFinite())
            if (x != 0f) assertTrue(y.toDouble() / x in .9699998..1.0300002)
        }
        assertTrue(dsp.snapshot().minGain >= .97)
        assertTrue(dsp.snapshot().maxGain <= 1.03)
    }

    @Test fun resetMatchesFreshSessionIncludingWarmup() {
        val retained = NormalEnvelopeDamper(sampleRate)
        repeat(sampleRate) { retained.process(sample(it)) }
        retained.reset()
        assertEquals(NormalEnvelopeSnapshot(0, 1.0, 1.0), retained.snapshot())
        val fresh = NormalEnvelopeDamper(sampleRate)
        repeat(sampleRate * 2) { assertEquals(fresh.process(sample(it)).toRawBits(), retained.process(sample(it)).toRawBits()) }
    }

    @Test fun samplePartitionsAreBitExact() {
        val count = 25000
        val source = FloatArray(count) { sample(it) }
        val first = NormalEnvelopeDamper(sampleRate)
        val expected = FloatArray(count) { first.process(source[it]) }
        for (size in intArrayOf(1, 333, 960, 997)) {
            val dsp = NormalEnvelopeDamper(sampleRate)
            var start = 0
            while (start < count) {
                for (i in start until min(count, start + size)) assertEquals(expected[i].toRawBits(), dsp.process(source[i]).toRawBits())
                start += size
            }
        }
    }

    @Test fun settledUnmodulatedToneStaysNearUnity() {
        val dsp = NormalEnvelopeDamper(sampleRate)
        var maximumError = 0.0
        repeat(sampleRate * 10) { index ->
            val x = sample(index, 0.0)
            val y = dsp.process(x)
            if (index >= sampleRate * 5) maximumError = max(maximumError, abs(y - x).toDouble())
        }
        assertTrue("Settled sample error $maximumError", maximumError < .0002)
    }

    @Test fun reducesWholeTraceSlowAmplitudeLineByTwentyFivePercent() {
        val ratio = amplitudeLinePowerRatio(0)
        assertTrue("Whole-trace target power ratio $ratio", ratio < .75)
    }

    @Test fun reducesPostTwoSecondSlowAmplitudeLineByTwentyFivePercent() {
        val ratio = amplitudeLinePowerRatio(2)
        assertTrue("Post-2s target power ratio $ratio", ratio < .75)
    }

    // Test-only exact-frequency projection of 10 ms RMS at 1 ms hops; no FFT in DSP.
    private fun amplitudeLinePowerRatio(fromSeconds: Int): Double {
        val dsp = NormalEnvelopeDamper(sampleRate)
        val oldRing = DoubleArray(480)
        val newRing = DoubleArray(480)
        var oldEnergy = 0.0
        var newEnergy = 0.0
        var oldSum = 0.0
        var newSum = 0.0
        var cosineSum = 0.0
        var sineSum = 0.0
        var oldReal = 0.0
        var oldImag = 0.0
        var newReal = 0.0
        var newImag = 0.0
        var count = 0
        repeat(sampleRate * 20) { index ->
            val x = sample(index).toDouble()
            val y = dsp.process(x.toFloat()).toDouble()
            val slot = index % 480
            oldEnergy += x * x - oldRing[slot]
            newEnergy += y * y - newRing[slot]
            oldRing[slot] = x * x
            newRing[slot] = y * y
            val start = index - 479
            if (start >= fromSeconds * sampleRate && start % 48 == 0) {
                val oldEnvelope = sqrt(max(0.0, oldEnergy / 480))
                val newEnvelope = sqrt(max(0.0, newEnergy / 480))
                val phase = 2 * PI * modulationHz * (start.toDouble() / sampleRate + .005)
                val c = cos(phase)
                val s = sin(phase)
                oldSum += oldEnvelope; newSum += newEnvelope
                cosineSum += c; sineSum += s
                oldReal += oldEnvelope * c; oldImag += oldEnvelope * s
                newReal += newEnvelope * c; newImag += newEnvelope * s
                count++
            }
        }
        oldReal -= oldSum / count * cosineSum; oldImag -= oldSum / count * sineSum
        newReal -= newSum / count * cosineSum; newImag -= newSum / count * sineSum
        return (newReal * newReal + newImag * newImag) / (oldReal * oldReal + oldImag * oldImag)
    }
}
