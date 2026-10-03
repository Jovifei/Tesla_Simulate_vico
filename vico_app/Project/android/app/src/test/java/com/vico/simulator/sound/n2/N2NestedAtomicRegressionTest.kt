package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import org.junit.Assert.*
import org.junit.Test

class N2NestedAtomicRegressionTest {
    @Test fun malformedFutureQueueCannotMutateLiveBaseline() {
        val baseline = HybridTestProfiles.create(); val profile = N2Profile.preregistered()
        val live = N2Source(baseline, profile, N2Mode.SE)
        repeat(12000) { live.sample(5000.0, .9, .9) }
        val before = live.snapshot()
        val future = N2Source(baseline, profile, N2Mode.SE)
        future.restore(before)
        repeat(100) { future.sample(4000.0, .05, .05) }
        val bad = future.snapshot(); bad.responses[0].l[0] = Double.NaN
        assertThrows(IllegalArgumentException::class.java) { live.restore(bad) }
        assertArrayEquals(before.baseline.scalars, live.snapshot().baseline.scalars, 0.0)
        val twin = N2Source(baseline, profile, N2Mode.SE); twin.restore(before)
        repeat(1000) { assertEquals(twin.sample(4000.0, .05, .05), live.sample(4000.0, .05, .05), 0f) }
    }

    @Test fun malformedNestedRendererStatePreservesLivePcm() {
        val baseline = HybridTestProfiles.create(); val profile = N2Profile.preregistered()
        fun renderer() = N2Renderer(baseline, profile, N2Mode.SE)
        fun state(n: Int) = SoundState(n*.02, 4000.0, 0.0, .5, .5, floatArrayOf(), false, .5, .5)
        val live = renderer()
        repeat(20) { live.render(state(it), 960) }
        val before = live.snapshot()
        val future = renderer(); future.restore(before); future.render(state(20), 960)
        val bad = future.snapshot(); bad.source.responses[0].l[0] = Double.NaN
        assertThrows(IllegalArgumentException::class.java) { live.restore(bad) }
        val twin = renderer(); twin.restore(before)
        repeat(5) { assertArrayEquals(twin.render(state(20+it), 960), live.render(state(20+it), 960), 0f) }
    }
}
