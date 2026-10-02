package com.vico.simulator.sound
import com.vico.simulator.sound.s17.C63BarkArrivalQueue
import org.junit.Assert.*
import org.junit.Test
class C63BarkArrivalHistoryTest {
    @Test fun registersSourceAndArrivalFramesAndBank() {
        val queue=C63BarkArrivalQueue(5900049,24)
        queue.inject(1,0,.4,100);queue.inject(2,1,.5,300)
        repeat(325){queue.step()}
        val rows=queue.arrivalHistory()
        assertArrayEquals(longArrayOf(100,300),rows.sourceFrames);assertArrayEquals(longArrayOf(124,324),rows.targetFrames)
        assertArrayEquals(intArrayOf(0,1),rows.banks);assertArrayEquals(intArrayOf(24,24),rows.delays);assertFalse(rows.truncated)
    }
}
