package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class PreviewPlaybackTest {
    @Test fun idleOwnerPreparesBeforeStarting() {
        val calls = mutableListOf<String>()
        assertTrue(startPreviewPlayback(false,
            { calls.add("prepare"); true }, { calls.add("start"); true }, { calls.add("restore") }))
        assertEquals(listOf("prepare", "start"), calls)
    }

    @Test fun runningOwnerKeepsItsControllerAndDoesNotRestart() {
        assertTrue(startPreviewPlayback(true,
            { fail("Running session must not reset"); false },
            { fail("Running session must not restart"); false },
            { fail("Running session must not restore"); }))
    }

    @Test fun rejectedPreparationRestoresAndAllowsRetry() {
        var selected = "preview"
        var starts = 0
        assertFalse(startPreviewPlayback(false, { false }, { starts++; true }, { selected = "original" }))
        assertEquals("original", selected)
        assertEquals(0, starts)
        assertTrue(startPreviewPlayback(false, { true }, { starts++; true }, { fail("Unexpected rollback") }))
        assertEquals(1, starts)
    }

    @Test fun failedStartRestoresExactlyOnce() {
        var restores = 0
        assertFalse(startPreviewPlayback(false, { true }, { false }, { restores++ }))
        assertEquals(1, restores)
    }
}
