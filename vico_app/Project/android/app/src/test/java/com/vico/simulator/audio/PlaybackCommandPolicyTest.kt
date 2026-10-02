package com.vico.simulator.audio

import org.junit.Assert.assertEquals
import org.junit.Test

class PlaybackCommandPolicyTest {

    @Test
    fun stopped_dashboard_requests_start() {
        assertEquals(PlaybackCommand.START, PlaybackCommandPolicy.commandFor(isRunning = false))
    }

    @Test
    fun running_dashboard_requests_stop() {
        assertEquals(PlaybackCommand.STOP, PlaybackCommandPolicy.commandFor(isRunning = true))
    }
}
