package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class SessionTimingTest {
    @Test fun retainsEarlyOutlierBeyondRollingWindow() {
        val timing=SessionTiming()
        timing.record(25_000_000)
        repeat(5000){timing.record(2_000_000)}
        assertEquals(5001L,timing.count)
        assertEquals(25_000_000L,timing.maxNs)
        assertEquals(1L,timing.deadlineMisses)
        assertEquals(2_000_000L,timing.percentile(99))
    }
    @Test fun percentileUsesConservativeFixedBins() {
        val timing=SessionTiming()
        assertNull(timing.percentile(99))
        timing.record(2_000_001)
        assertEquals(2_100_000L,timing.percentile(99))
        assertThrows(IllegalArgumentException::class.java){timing.record(-1)}
    }
}
