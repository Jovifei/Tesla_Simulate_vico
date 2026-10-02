package com.vico.simulator.sound
import com.vico.simulator.sound.s17.*
import com.vico.simulator.sound.s18.*
import org.junit.Assert.*
import org.junit.Test

class C63HybridSourceTest {
    @Test fun textureControlExactlyMatchesFrozenT() {
        val old=C63AR2Source(C63AR2Profile(),C63AR2Mode.T);val fresh=C63HybridSource(HybridTestProfiles.create(),C63HybridMode.T)
        repeat(120000){n->val closed=n>96000;val r=if(closed)4000.0 else 5000.0;val l=if(closed).05 else .9
            assertEquals(old.sample(r,l,l),fresh.sample(r,l,l),0f)}
    }
    @Test fun replacingBarkAndEventNeverChangesRawLowerStems() {
        val t=C63HybridSource(HybridTestProfiles.create(),C63HybridMode.T);val se=C63HybridSource(HybridTestProfiles.create(),C63HybridMode.SE)
        repeat(120000){n->val closed=n>96000;val r=if(closed)4000.0 else 5000.0;val l=if(closed).05 else .9;t.sample(r,l,l);se.sample(r,l,l)
            for(i in intArrayOf(0,2,3,5,6))assertEquals(t.lastStems[i],se.lastStems[i],0.0)}
    }
    @Test fun eventOffKeepsOtherStateAndRandomSequencesExact() {
        val on=C63HybridSource(HybridTestProfiles.create(),C63HybridMode.SE,true);val off=C63HybridSource(HybridTestProfiles.create(),C63HybridMode.SE,false)
        repeat(121000){n->val closed=n>=96000;val r=if(closed)4000.0 else 5000.0;val l=if(closed).05 else .9;on.sample(r,l,l);off.sample(r,l,l)
            for(i in intArrayOf(0,1,2,3,5,6))assertEquals(on.lastStems[i],off.lastStems[i],0.0);assertEquals(0.0,off.lastStems[4],0.0)}
        assertArrayEquals(on.eventObservation().arrivalFrames,off.eventObservation().arrivalFrames)
    }
    @Test fun coastGateChangesNewDriveWithoutCuttingTheLowBody() {
        val s=C63HybridSource(HybridTestProfiles.create(),C63HybridMode.S)
        repeat(96000){s.sample(5000.0,.9,.9)};repeat(24000){s.sample(4000.0,.05,.05)}
        assertTrue(s.driveState<1e-5);assertTrue(s.lastStems[3]!=0.0)
    }
}
