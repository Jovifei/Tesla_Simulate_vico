package com.vico.simulator.sound.n2

import com.vico.simulator.sound.s18.C63FiniteResponseSource
import org.junit.Assert.*
import org.junit.Test

class N2EventAtomicRegressionTest {
    @Test fun rejectedInnerQueueCannotAdvanceLiveOccurrence() {
        val profile = N2Profile.preregistered()
        val live = N2EventProcess(profile)
        repeat(96000) { n -> live.sample(5000.0, .9, .9, n % 144 == 0) }
        repeat(4000) { n -> live.sample(4000.0, .05, .05, n % 180 == 0) }
        val before = live.snapshot()
        val future = N2EventProcess(profile)
        future.restore(before)
        repeat(100) { n -> future.sample(4000.0, .05, .05, n % 180 == 0) }
        val saved = future.snapshot()
        val q = saved.response
        val badQueue = C63FiniteResponseSource.Snapshot(q.identity, q.l, q.r, Int.MAX_VALUE,
            q.lastEvent, q.frames, q.events, q.pending, q.left, q.right)
        val bad = N2EventProcess.Snapshot(saved.key, saved.occurrence, badQueue,
            saved.responseRng, saved.angle, saved.signal)
        assertThrows(IllegalArgumentException::class.java) { live.restore(bad) }
        val after = live.snapshot()
        assertArrayEquals(before.occurrence.counters, after.occurrence.counters)
        assertArrayEquals(before.occurrence.scalars, after.occurrence.scalars, 0.0)
        assertEquals(before.responseRng, after.responseRng)
    }
}
