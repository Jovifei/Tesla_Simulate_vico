package com.vico.simulator.sound
import com.vico.simulator.sound.s18.C63HybridNoise
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.sqrt

class C63HybridNoiseTest {
    @Test fun noiseSnapshotResumesExactIndependentStream() {
        val a=C63HybridNoise(5900067L,doubleArrayOf(.5,.5,.5,.5))
        repeat(5000){a.sample()};val b=C63HybridNoise(5900067L,doubleArrayOf(.5,.5,.5,.5));b.restore(a.snapshot())
        repeat(5000){assertEquals(a.sample(),b.sample(),0.0)}
    }
    @Test fun coloredNoiseHasFixedUnitPowerWithoutLiveNormalization() {
        val a=C63HybridNoise(5900067L,doubleArrayOf(.5,.5,.5,.5));repeat(24000){a.sample()}
        var energy=0.0;repeat(96000){val v=a.sample();assertTrue(v.isFinite());energy+=v*v}
        assertEquals(1.0,sqrt(energy/96000),.07)
    }
    @Test fun malformedNoiseProfileIsRejectedBeforeStateExists() {
        assertThrows(IllegalArgumentException::class.java){C63HybridNoise(0,doubleArrayOf(.5,.5,.5,.5))}
        assertThrows(IllegalArgumentException::class.java){C63HybridNoise(1,doubleArrayOf(Double.NaN,.5,.5,.5))}
    }
}
