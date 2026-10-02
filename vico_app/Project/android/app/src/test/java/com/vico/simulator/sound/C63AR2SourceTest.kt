package com.vico.simulator.sound
import com.vico.simulator.sound.s16.*
import com.vico.simulator.sound.s17.*
import org.junit.Assert.*
import org.junit.Test
class C63AR2SourceTest {
    @Test fun textureOnlySourceReproducesFrozenDependencyWithNonzeroAudio() {
        val old=C63AudibleSource(C63AudibleProfile(textureScale=9.786453030584157),C63AudibleMode.S)
        val t=C63AR2Source(C63AR2Profile(),C63AR2Mode.T);var energy=0.0
        repeat(24000){val value=t.sample(4000.0,.64,.64);energy+=value*value;assertEquals(old.sample(4000.0,.64,.64),value,0f)}
        assertTrue(energy>0)
    }
    @Test fun zeroArrivalControlExactlyReproducesTextureOnlyT() {
        val t=C63AR2Source(C63AR2Profile(),C63AR2Mode.T)
        val zero=C63AR2Source(C63AR2Profile(fixedDelay=0),C63AR2Mode.S2)
        repeat(24000){assertEquals(t.sample(4000.0,.64,.64),zero.sample(4000.0,.64,.64),0f)}
    }
    @Test fun barkRngDoesNotChangeOtherStemsOrAfterfire() {
        val t=C63AR2Source(C63AR2Profile(),C63AR2Mode.E2);val mixed=C63AR2Source(C63AR2Profile(),C63AR2Mode.SE2)
        repeat(120000){n->val throttle=if(n<96000).9 else .05;t.sample(4000.0,throttle,throttle);mixed.sample(4000.0,throttle,throttle)
            for(stem in listOf(0,2,3,4,5,6))assertEquals(t.lastStems[stem],mixed.lastStems[stem],0.0)}
    }
    @Test fun sourceSnapshotPreservesQueueAndEpisodesAndActualInvalidInputGate() {
        val a=C63AR2Source(C63AR2Profile(),C63AR2Mode.SE2);repeat(96000){a.sample(5000.0,.9,.9)}
        val b=C63AR2Source(C63AR2Profile(),C63AR2Mode.SE2);b.restore(a.snapshot())
        repeat(26000){assertEquals(a.sample(4000.0,.05,.05,false),b.sample(4000.0,.05,.05,false),0f)}
        assertEquals(0L,a.afterfireEvents)
        assertEquals(a.arrivalInjected,a.arrivalEmitted+a.arrivalPending,1e-8)
    }
}
