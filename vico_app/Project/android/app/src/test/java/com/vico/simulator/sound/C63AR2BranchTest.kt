package com.vico.simulator.sound
import com.vico.simulator.sound.s17.*
import org.junit.Assert.*
import org.junit.Test
class C63AR2BranchTest {
    @Test fun E2AndSE2ShareEveryAfterfireEventAndAmplitudeButOnlySE2HasArrivalDispersion() {
        val e=C63AR2Source(C63AR2Profile(),C63AR2Mode.E2);val se=C63AR2Source(C63AR2Profile(),C63AR2Mode.SE2)
        repeat(96000){e.sample(5000.0,.9,.9);se.sample(5000.0,.9,.9)}
        repeat(24960){e.sample(4000.0,.25,.05);se.sample(4000.0,.25,.05)
            assertEquals(e.lastStems[4],se.lastStems[4],0.0)}
        assertTrue("E2 source events="+e.afterfireEvents+" episodes="+e.eventObservation().episodes+" thermal="+e.afterfireThermal+" age="+e.afterfireAgeFrames,e.afterfireEvents>0)
        assertEquals(0.0,e.arrivalInjected,0.0)
        assertTrue("SE2 bark arrivals=\${se.arrivalInjected}; AF events=\${se.afterfireEvents}",se.arrivalInjected>0)
    }
    @Test fun reportedArrivalsAndDistinctImpulsesAreNotAliased() {
        val queue=C63BarkArrivalQueue(5900049,0)
        queue.inject(1,0,.4);queue.inject(2,1,.5);queue.step()
        assertEquals(2L,queue.rawArrivals);assertEquals(1L,queue.distinctImpulseFrames)
        queue.step();assertEquals(1L,queue.distinctImpulseFrames)
    }
    @Test fun rawAfArrivalsAndImpulseFramesAndEpisodesAreObservableOnActualRenderer() {
        val renderer=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.E2,true)
        fun block(time:Double,rpm:Double,load:Double,throttle:Double)=renderer.render(
            SoundState(time,rpm,rpm/15,load,load,floatArrayOf(),false,throttle,load),960)
        repeat(100){block(it*.02,5000.0,.9,.9)}
        repeat(26){block(2+it*.02,4000.0,.25,.05)}
        val report=renderer.eventObservation()
        assertTrue(report.episodes>0);assertEquals(report.rawArrivals,report.arrivalFrames.size.toLong())
        assertEquals(report.rawArrivals,report.arrivalAmplitudes.size.toLong())
        assertTrue(report.distinctImpulseFrames<=report.rawArrivals)
        assertEquals(report.distinctImpulseFrames,report.impulseFrames.size.toLong())
        assertEquals(report.impulseFrames.size,report.impulseAmplitudes.size)
    }
    @Test fun rendererRecordsEventsUsingActualSampleClockAndValidity() {
        val renderer=C63AR2Renderer(C63AR2Profile(fixedDelay=24),C63AR2Mode.SE2,true)
        repeat(100){n->renderer.render(SoundState(n*.02,5000.0,5000.0/15,.9,.9,floatArrayOf(),false,.9,.9),960)}
        repeat(26){n->renderer.render(SoundState(2+n*.02,4000.0,4000.0/15,.25,.25,floatArrayOf(),false,.05,.25),960)}
        val beforeInvalid=renderer.eventObservation().rawArrivals
        repeat(40){n->renderer.render(SoundState(2.52+n*.02,4000.0,4000.0/15,.25,.25,floatArrayOf(),false,.05,.25),960,validInput=false)}
        val events=renderer.eventObservation();val arrivals=renderer.barkArrivalHistory()!!
        assertTrue(arrivals.truncated.not());assertEquals(setOf(24),arrivals.delays.toSet())
        assertTrue(events.rawArrivals>0);assertEquals(beforeInvalid,events.rawArrivals);val savedArrivals=events.rawArrivals
        assertEquals(savedArrivals,renderer.eventObservation().rawArrivals)
        assertTrue(events.distinctImpulseFrames<=savedArrivals);assertTrue(events.distinctImpulseFrames>0)
        assertEquals(events.arrivalFrames.size,events.arrivalAmplitudes.size)
    }
}
