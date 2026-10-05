package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class N2SourceTest {
    private fun source(mode: N2Mode, audible: Boolean = true, profile: N2Profile = N2Profile.preregistered()) =
        N2Source(HybridTestProfiles.create(), profile, mode, audible)

    @Test
    fun replacingBarkAndEventDoesNotChangeFrozenLowerStems() {
        val t = source(N2Mode.T)
        val se = source(N2Mode.SE)
        repeat(24000) { n ->
            val closed = n >= 18000
            val rpm = if (closed) 4000.0 else 5000.0
            val load = if (closed) .05 else .9
            t.sample(rpm, load, load)
            se.sample(rpm, load, load)
            for (index in intArrayOf(0, 2, 3, 5, 6)) {
                assertEquals(t.lastStems[index], se.lastStems[index], 0.0)
            }
        }
    }

    @Test
    fun sourceSnapshotRestoresQueuesTextureRngAndEventStateExactly() {
        val a = source(N2Mode.SE)
        repeat(96000) { a.sample(5000.0, .9, .9) }
        repeat(4000) { a.sample(4000.0, .05, .05) }
        val saved = a.snapshot()
        val b = source(N2Mode.SE)
        b.restore(saved)
        repeat(16000) { n ->
            val rpm = if (n < 4000) 4000.0 else 2800.0
            val load = if (n < 4000) .05 else .35
            assertEquals(a.sample(rpm, load, load), b.sample(rpm, load, load), 0.0f)
        }
    }

    @Test
    fun wrongProfileAndCorruptSnapshotAreRejectedBeforeRestore() {
        val original = N2Profile.preregistered()
        val a = source(N2Mode.S, profile = original)
        repeat(3000) { a.sample(4200.0, .7, .7) }
        val saved = a.snapshot()

        val other = N2Profile(
            Array(N2Profile.BASIS_COUNT) { original.basis(it) },
            original.coefficients(),
            original.eventResponse(),
            original.eventNoiseA(),
            original.eventNoiseB(),
            sourceScale = original.sourceScale,
            randomFraction = original.randomFraction,
            eventScale = original.eventScale,
            eventNoiseFraction = original.eventNoiseFraction,
            sourceSeed = original.sourceSeed + 1L,
            occurrenceSeed = original.occurrenceSeed,
            responseSeed = original.responseSeed,
        )
        assertThrows(IllegalArgumentException::class.java) {
            source(N2Mode.S, profile = other).restore(saved)
        }

        val badScalars = saved.scalars.copyOf().also { it[0] = Double.NaN }
        val corrupt = N2Source.Snapshot(
            saved.key,
            saved.baseline,
            saved.responses,
            saved.event,
            saved.counters.copyOf(),
            badScalars,
            saved.stems.copyOf(),
        )
        assertThrows(IllegalArgumentException::class.java) { a.restore(corrupt) }
    }

    @Test
    fun eventOffKeepsOccurrenceAndResponseStreamsWhileMutingOnlyEventStem() {
        val on = source(N2Mode.E, true)
        val off = source(N2Mode.E, false)
        repeat(96000) {
            on.sample(5000.0, .9, .9)
            off.sample(5000.0, .9, .9)
        }

        var guard = 0
        while (on.eventObservation().rawArrivals < 2L && guard++ < 24960) {
            on.sample(4000.0, .05, .05)
            off.sample(4000.0, .05, .05)
            for (index in intArrayOf(0, 1, 2, 3, 5, 6)) {
                assertEquals(on.lastStems[index], off.lastStems[index], 0.0)
            }
            assertEquals(0.0, off.lastStems[4], 0.0)
        }

        val onObs = on.eventObservation()
        val offObs = off.eventObservation()
        assertTrue(onObs.rawArrivals >= 2L)
        assertArrayEquals(onObs.arrivalFrames, offObs.arrivalFrames)
        assertArrayEquals(onObs.arrivalAmplitudes, offObs.arrivalAmplitudes, 0.0)
        assertTrue(on.pendingFrames > 0)

        var pending = on.pendingFrames
        repeat(pending) {
            on.sample(0.0, 0.0, 0.0, validInput = false)
        }
        assertEquals(0, on.pendingFrames)
    }
}
