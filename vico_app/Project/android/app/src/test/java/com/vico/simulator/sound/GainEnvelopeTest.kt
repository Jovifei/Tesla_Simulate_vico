package com.vico.simulator.sound

import org.junit.Assert.assertTrue
import org.junit.Test

class GainEnvelopeTest {

    @Test
    fun transitions_to_silence_over_multiple_audio_blocks() {
        val envelope = GainEnvelope()
        repeat(12) { envelope.step(true) }
        val beforeMute = envelope.value

        envelope.step(false)

        assertTrue(beforeMute > envelope.value)
        assertTrue("first muted block must not be a hard cut", envelope.value > 0f)
        repeat(32) { envelope.step(false) }
        assertTrue(envelope.value < 0.001f)
    }
}
