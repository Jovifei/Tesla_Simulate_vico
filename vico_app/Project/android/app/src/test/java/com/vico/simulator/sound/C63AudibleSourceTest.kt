package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63SourcePrototype
import com.vico.simulator.sound.s16.*
import org.junit.Assert.*
import org.junit.Test
class C63AudibleSourceTest {
    @Test fun disabledChangesExactlyReproduceFrozenSourceIncludingEvents() {
        val original=C63SourcePrototype();val candidate=C63AudibleSource(C63AudibleProfile(),C63AudibleMode.AH)
        repeat(144000){n->val throttle=if(n<96000).9 else .05
            assertEquals(original.sample(4000.0,throttle,throttle),candidate.sample(4000.0,throttle,throttle),0f)
            assertArrayEquals(original.lastStems,candidate.lastStems,0.0)}
    }
    @Test fun sustainedChangesDoNotAlterProtectedStems() {
        val original=C63SourcePrototype();val candidate=C63AudibleSource(C63AudibleProfile(),C63AudibleMode.S)
        repeat(24000){original.sample(2900.0,.64,.64);candidate.sample(2900.0,.64,.64)
            for(stem in listOf(0,2,4,5,6))assertEquals(original.lastStems[stem],candidate.lastStems[stem],0.0)}
    }
    @Test fun eventOnlyChangeLeavesOpenThrottleBodyExact() {
        val original=C63SourcePrototype();val candidate=C63AudibleSource(C63AudibleProfile(),C63AudibleMode.E)
        repeat(96000){assertEquals(original.sample(4000.0,.9,.9),candidate.sample(4000.0,.9,.9),0f)}
    }
    @Test fun snapshotKeepsTextureEpisodeAndDiagnosticStemsAndRejectsInvalidInput() {
        val a=C63AudibleSource(C63AudibleProfile(),C63AudibleMode.SE)
        repeat(96000){a.sample(4000.0,.9,.9)};repeat(10000){a.sample(4000.0,.05,.05)}
        val b=C63AudibleSource(C63AudibleProfile(),C63AudibleMode.SE);b.restore(a.snapshot())
        assertArrayEquals(a.lastStems,b.lastStems,0.0)
        assertThrows(IllegalArgumentException::class.java){a.sample(Double.NaN,.05,.05)}
        repeat(24000){assertEquals(a.sample(4000.0,.05,.05),b.sample(4000.0,.05,.05),0f)}
        assertThrows(IllegalArgumentException::class.java){C63AudibleSource(C63AudibleProfile(textureScale=2.0),C63AudibleMode.SE).restore(a.snapshot())}
        assertThrows(IllegalArgumentException::class.java){C63AudibleProfile(textureScale=Double.NaN)}
    }
}
