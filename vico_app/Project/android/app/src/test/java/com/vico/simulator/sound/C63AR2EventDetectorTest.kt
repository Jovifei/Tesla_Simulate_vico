package com.vico.simulator.sound
import com.vico.simulator.sound.s17.C63AR2EventMetrics
import org.junit.Assert.*
import org.junit.Test
class C63AR2EventDetectorTest {
    @Test fun onlyTwoSidedSixDecibelValleysDefineASeparatedTransient() {
        val both=DoubleArray(80){if(it==40)1.0 else if(it==39 || it==41).3 else if(it==38 || it==42).1 else 0.0}
        val oneSided=DoubleArray(80){if(it==40)1.0 else if(it==39).1 else if(it>40).8 else 0.0}
        assertTrue(C63AR2EventMetrics.isolatedPeak(both,40,28,66))
        assertFalse(C63AR2EventMetrics.isolatedPeak(oneSided,40,28,66))
        assertFalse(C63AR2EventMetrics.isolatedPeak(doubleArrayOf(1.0,.3,.1,0.0),0,0,4))
        assertFalse(C63AR2EventMetrics.isolatedPeak(doubleArrayOf(0.0,.1,.3,1.0),3,0,4))
    }
    @Test fun sameFrameRawArrivalsCollapseToOneObservableImpulse() {
        val report=C63AR2EventMetrics.countImpulses(longArrayOf(12,12,12,20,25))
        assertEquals(5L,report.rawArrivals);assertEquals(3L,report.distinctImpulses)
        val merged=C63AR2EventMetrics.mergeArrivals(longArrayOf(12,12,12,20,25),doubleArrayOf(.2,.3,.4,.5,.6))
        assertEquals(5,merged.rawArrivals);assertArrayEquals(longArrayOf(12,20,25),merged.frames)
        assertArrayEquals(doubleArrayOf(.9,.5,.6),merged.areas,0.0)
    }
    @Test fun detectorRejectsNaNAndMalformedBoundaryInsteadOfPass() {
        assertThrows(IllegalArgumentException::class.java){C63AR2EventMetrics.isolatedPeak(doubleArrayOf(0.0,Double.NaN,1.0,0.0),2,0,4)}
        assertThrows(IllegalArgumentException::class.java){C63AR2EventMetrics.isolatedPeak(doubleArrayOf(0.0,1.0),2,0,2)}
    }
}
