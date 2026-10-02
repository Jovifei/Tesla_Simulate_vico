package com.vico.simulator.sound
import com.vico.simulator.sound.s17.C63BarkArrivalQueue
import org.junit.Assert.*
import org.junit.Test
class C63BarkArrivalQueueTest {
    @Test fun zeroAndFixedDelayPreserveAreaBankAndPendingTail() {
        val zero=C63BarkArrivalQueue(5900049,0);zero.inject(0,1,.8);zero.step()
        assertEquals(0.0,zero.left,0.0);assertEquals(.8,zero.right,0.0)
        val delayed=C63BarkArrivalQueue(5900049,24);delayed.inject(0,0,1.2)
        repeat(24){delayed.step();assertEquals(0.0,delayed.left,0.0)}
        assertEquals(1.2,delayed.pendingArea(),1e-12);delayed.step()
        assertEquals(1.2,delayed.left,0.0);assertEquals(delayed.injectedArea,delayed.emittedArea,1e-12)
    }
    @Test fun randomStateAndBothQueuesRestoreAcrossBlockBoundary() {
        val a=C63BarkArrivalQueue(5900049)
        repeat(100){n->if(n%17==0)a.inject(n.toLong(),n%2,.7);a.step()}
        val b=C63BarkArrivalQueue(5900049);b.restore(a.snapshot())
        repeat(1000){n->if(n%17==0){a.inject(100+n.toLong(),n%2,.7);b.inject(100+n.toLong(),n%2,.7)};a.step();b.step()
            assertEquals(a.left,b.left,0.0);assertEquals(a.right,b.right,0.0)}
        assertEquals(a.injectedArea,a.emittedArea+a.pendingArea(),1e-10)
    }
    @Test fun duplicateOrInvalidInjectionIsRejectedBeforeRandomMutation() {
        val a=C63BarkArrivalQueue(5900049);val b=C63BarkArrivalQueue(5900049)
        a.inject(0,0,1.0);b.inject(0,0,1.0)
        assertThrows(IllegalArgumentException::class.java){a.inject(0,0,1.0)}
        assertThrows(IllegalArgumentException::class.java){a.inject(1,2,1.0)}
        repeat(100){a.step();b.step();assertEquals(a.left,b.left,0.0)}
    }
}
