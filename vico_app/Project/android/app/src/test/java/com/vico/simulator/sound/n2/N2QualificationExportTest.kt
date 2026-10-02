package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class N2QualificationExportTest {
    private fun state(n: Int) = SoundState(
        timeS = n * .02,
        rpm = 3500.0 + n * 100.0,
        frequencyHz = 0.0,
        amplitude = .6,
        brightness = .7,
        harmonics = floatArrayOf(),
        muted = false,
        throttle = .6,
        load = .7,
    )

    @Test
    fun emptyTrajectoryProducesNoEvidence() {
        assertTrue(
            N2QualificationExport.renderAll(
                emptyList(),
                HybridTestProfiles.create(),
                N2Profile.preregistered(),
            ).isEmpty()
        )
    }

    @Test
    fun exportContainsTSESEAndOnlyTheRegisteredEventOffControls() {
        val states = (0..2).map(::state)
        val results = N2QualificationExport.renderAll(
            states,
            HybridTestProfiles.create(),
            N2Profile.preregistered(),
        )
        assertEquals(6, results.size)
        assertEquals(
            listOf(
                N2Mode.T to true,
                N2Mode.S to true,
                N2Mode.E to true,
                N2Mode.E to false,
                N2Mode.SE to true,
                N2Mode.SE to false,
            ),
            results.map { it.mode to it.eventsAudible },
        )
        results.forEach {
            assertEquals(states.size * 960, it.frames)
            assertEquals(48000, it.sampleRate)
            assertEquals(1, it.channels)
            assertTrue(it.measurement.evidenceValid)
            assertFalse(it.pcm.isEmpty())
        }
    }
}
