package com.vico.simulator.sound
import com.vico.simulator.sound.s18.C63FiniteResponseSource
import org.junit.Assert.*
import org.junit.Test

class C63FiniteResponseSourceTest {
    @Test fun signedResponsePreservesBankAndOverlappingTail() {
        val source=C63FiniteResponseSource(doubleArrayOf(1.0,-.5,-.5))
        source.inject(0,0,.4);source.step();assertEquals(.4,source.left,0.0);assertEquals(0.0,source.right,0.0)
        source.inject(1,1,.2);source.step();assertEquals(-.2,source.left,0.0);assertEquals(.2,source.right,0.0)
        source.step();assertEquals(-.2,source.left,0.0);assertEquals(-.1,source.right,0.0)
        source.step();assertEquals(-.1,source.right,0.0);assertEquals(0,source.pendingFrames)
        assertEquals(2L,source.events)
    }
    @Test fun snapshotRestoresUnconsumedKernelTail() {
        val kernel=DoubleArray(2048){if(it==0)1.0 else if(it==2047)-1.0 else 0.0}
        val a=C63FiniteResponseSource(kernel);a.inject(0,1,.7);repeat(192){a.step()}
        val b=C63FiniteResponseSource(kernel);b.restore(a.snapshot())
        repeat(2200){a.step();b.step();assertEquals(a.left,b.left,0.0);assertEquals(a.right,b.right,0.0)}
        assertEquals(0,a.pendingFrames)
    }
    @Test fun finiteResponseNeverDropsEndTailOrOverwritesAtWrap() {
        val a=C63FiniteResponseSource(doubleArrayOf(1.0,-1.0))
        repeat(50){n->a.inject(n.toLong(),n%2,.5);a.step();a.step()}
        assertEquals(50L,a.events);assertEquals(0,a.pendingFrames);assertEquals(0.0,a.pendingEnergy(),0.0)
    }
    @Test fun invalidAmplitudeAndDuplicateIdCannotMutateState() {
        val a=C63FiniteResponseSource(doubleArrayOf(1.0,-1.0));a.inject(0,0,.5)
        assertThrows(IllegalArgumentException::class.java){a.inject(1,0,Double.NaN)}
        assertThrows(IllegalArgumentException::class.java){a.inject(0,0,.5)}
        a.step();assertEquals(.5,a.left,0.0);assertEquals(1L,a.events)
    }
    @Test fun differentKernelCannotAcceptSnapshot() {
        val a=C63FiniteResponseSource(doubleArrayOf(1.0,-1.0));val b=C63FiniteResponseSource(doubleArrayOf(.5,-.5))
        assertThrows(IllegalArgumentException::class.java){b.restore(a.snapshot())}
    }
}
