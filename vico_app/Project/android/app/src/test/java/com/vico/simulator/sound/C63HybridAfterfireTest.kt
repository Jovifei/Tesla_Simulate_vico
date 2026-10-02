package com.vico.simulator.sound
import com.vico.simulator.sound.s17.C63AR2AfterfireRuntime
import com.vico.simulator.sound.s18.C63HybridAfterfire
import org.junit.Assert.*
import org.junit.Test

class C63HybridAfterfireTest {
    @Test fun changingResponseCannotChangeOccurrenceFramesOrAmplitudes() {
        val old=C63AR2AfterfireRuntime(5900017L,0.0);val fresh=C63HybridAfterfire(HybridTestProfiles.create())
        repeat(121000){n->val closed=n>=96000;val r=if(closed)4000.0 else 5000.0;val l=if(closed).05 else .9
            old.sample(r,l,l,n%180==0);fresh.sample(r,l,l,n%180==0)}
        assertTrue(old.events>0);val a=old.observation();val b=fresh.observation()
        assertEquals(a.rawArrivals,b.rawArrivals);assertArrayEquals(a.arrivalFrames,b.arrivalFrames)
        assertArrayEquals(a.arrivalAmplitudes,b.arrivalAmplitudes,0.0)
    }
    @Test fun snapshotResumesResponseNoiseAndTailExactly() {
        val a=C63HybridAfterfire(HybridTestProfiles.create())
        repeat(104000){n->a.sample(if(n<96000)5000.0 else 4000.0,if(n<96000).9 else .05,if(n<96000).9 else .05,n%180==0)}
        val b=C63HybridAfterfire(HybridTestProfiles.create());b.restore(a.snapshot())
        repeat(16000){n->assertEquals(a.sample(4000.0,.05,.05,n%180==0),b.sample(4000.0,.05,.05,n%180==0),0.0)}
    }
    @Test fun invalidInputStopsNewEventsAndKeepsFiniteTail() {
        val a=C63HybridAfterfire(HybridTestProfiles.create())
        repeat(100000){n->a.sample(5000.0,.9,if(n<96000).9 else .05,n%160==0)}
        val before=a.observation().rawArrivals
        repeat(13000){assertTrue(a.sample(4000.0,.05,.05,true,false).isFinite())}
        assertEquals(before,a.observation().rawArrivals);assertEquals(0,a.pendingFrames)
    }
}
