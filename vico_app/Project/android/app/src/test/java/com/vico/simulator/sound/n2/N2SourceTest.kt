package com.vico.simulator.sound.n2

import org.junit.Assert.assertTrue
import org.junit.Test

class N2SourceTest {
    @Test fun deterministicEvent() {
        val a = N2Source().event()
        val b = N2Source().event()
        assertTrue(a.contentEquals(b))
    }

    @Test fun finiteOutput() {
        assertTrue(N2Measurement.finite(N2Source().continuous(333, 0.0)))
    }
}
