package com.vico.simulator.sound
import com.vico.simulator.sound.s16.C63AfterfireRuntime
import org.junit.Assert.*
import org.junit.Test
class C63AfterfireRuntimeTest {
    private fun warm(runtime:C63AfterfireRuntime) {repeat(96000){runtime.sample(5000.0,.9,.9,it%144==0)}}
    @Test fun smallSeedInitializationDoesNotBiasEveryFirstEventToEpisodeEnd() {
        var delay=0.0
        for(seed in 1L..16L){val runtime=C63AfterfireRuntime(seed);warm(runtime)
            repeat(24960){runtime.sample(4000.0,.05,.05,it%180==0)}
            delay+=(runtime.eventFrames().firstOrNull()?.minus(96000) ?: 24960)/48000.0}
        assertTrue("Initial hazard draws must not be systematically tiny",delay/16<.1)
    }
    @Test fun coldAndOpenThrottleDoNotCreateEvents() {
        val cold=C63AfterfireRuntime(42)
        repeat(25000){cold.sample(4000.0,.05,.05,it%180==0)}
        assertEquals(0L,cold.events)
        val hot=C63AfterfireRuntime(42);warm(hot)
        assertEquals(0L,hot.events)
    }
    @Test fun deterministicEpisodesDoNotForceTwoUniformHits() {
        val a=C63AfterfireRuntime(42);val b=C63AfterfireRuntime(42);warm(a);warm(b)
        repeat(24960){n->assertEquals(a.sample(4000.0,.05,.05,n%180==0),b.sample(4000.0,.05,.05,n%180==0),0.0)}
        assertTrue(a.events>2)
        val times=a.eventFrames();assertArrayEquals(times,b.eventFrames())
        val intervals=times.drop(1).zip(times.asList()).map{it.first-it.second}.toSet()
        assertTrue(intervals.size>2)
    }
    @Test fun reopeningAndMissingInputCancelNewEventsButNotTail() {
        val a=C63AfterfireRuntime(42);warm(a)
        for(n in 0 until 10000){a.sample(4000.0,.05,.05,true);if(a.events>0L)break}
        assertTrue(a.events>0L)
        val count=a.events;var tailEnergy=0.0
        repeat(200){val value=a.sample(4000.0,.9,.9,true);tailEnergy+=value*value}
        assertEquals(count,a.events);assertTrue(tailEnergy>0)
        repeat(25000){a.sample(4000.0,.05,.05,true,validInput=false)}
        assertEquals(count,a.events)
    }
    @Test fun snapshotsAndInvalidInputPreserveEntireEpisode() {
        val a=C63AfterfireRuntime(42);warm(a);repeat(700){a.sample(4000.0,.05,.05,it%180==0)}
        val b=C63AfterfireRuntime(42);b.restore(a.snapshot())
        assertThrows(IllegalArgumentException::class.java){a.sample(Double.NaN,.05,.05,true)}
        repeat(24960){n->assertEquals(a.sample(4000.0,.05,.05,n%180==0),b.sample(4000.0,.05,.05,n%180==0),0.0)}
        assertArrayEquals(a.eventFrames(),b.eventFrames())
        assertThrows(IllegalArgumentException::class.java){C63AfterfireRuntime(43).restore(a.snapshot())}
    }
}
