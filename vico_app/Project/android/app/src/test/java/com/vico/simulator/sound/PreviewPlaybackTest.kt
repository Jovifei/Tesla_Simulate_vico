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

    @Test fun busyOwnerRejectsWithoutCallbacks() {
        assertFalse(startPreviewPlayback(true,
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

    @Test fun preparationExceptionRestoresExactlyOnceWithoutStarting() {
        var restores = 0
        var starts = 0
        assertFalse(startPreviewPlayback(false, { throw IllegalStateException("prepare failure") },
            { starts++; true }, { restores++ }))
        assertEquals(0, starts)
        assertEquals(1, restores)
    }

    @Test fun startExceptionDefersRollbackUntilItsWriterExits() {
        var writerAlive = false
        var stops = 0
        var restores = 0
        val pending = mutableListOf<Runnable>()
        val finish = restoration({ true }, { writerAlive }, { stops++ },
            { restores++ }, { pending.add(it) }, { fail("Unexpected timeout") })
        assertFalse(startPreviewPlayback(false, { true },
            { writerAlive = true; throw IllegalArgumentException("start failure") }, { finish.run() }))
        assertEquals(1, stops)
        assertEquals(0, restores)
        writerAlive = false
        pending.removeAt(0).run()
        finish.run()
        assertEquals(1, stops)
        assertEquals(1, restores)
    }

    @Test fun vmErrorIsNotSwallowedOrRestored() {
        assertThrows(InternalError::class.java) {
            startPreviewPlayback(false, { throw InternalError("controlled VM error") },
                { fail("VM error must not start playback"); false }, { fail("VM error must not roll back") })
        }
    }

    @Test fun rollbackExceptionIsNotRetried() {
        var restores = 0
        assertThrows(IllegalStateException::class.java) {
            startPreviewPlayback(false, { false }, { false },
                { restores++; throw IllegalStateException("controlled rollback failure") })
        }
        assertEquals(1, restores)
    }

    // Reflection permits the same tests to fail as assertions on the unmodified source.
    private fun restoration(
        owns: () -> Boolean, busy: () -> Boolean, stop: () -> Unit,
        restore: () -> Unit, retry: (Runnable) -> Unit, timeout: () -> Unit,
        maxBusyChecks: Int = 50,
    ): Runnable {
        val method = Class.forName("com.vico.simulator.sound.PreviewPlaybackKt")
            .declaredMethods.singleOrNull { it.name == "restorePreviewWhenIdle" && it.parameterCount == 7 }
        assertNotNull("Preview completion needs owned stop-before-restore with bounded quiescence checks", method)
        return method!!.invoke(null, owns, busy, stop, restore, retry, timeout, maxBusyChecks) as Runnable
    }

    @Test fun idleCompletionStopsBeforeCheckingAndRestoring() {
        val calls = mutableListOf<String>()
        val finish = restoration({ true }, { calls.add("busy"); false }, { calls.add("stop") },
            { calls.add("restore") }, { fail("Idle writer needs no retry") }, { fail("Unexpected timeout") })
        finish.run()
        finish.run()
        assertEquals(listOf("stop", "busy", "restore"), calls)
    }

    @Test fun callbackWhileWriterStillAliveDefersRestore() {
        var writerAlive = true
        val calls = mutableListOf<String>()
        val pending = mutableListOf<Runnable>()
        val finish = restoration({ true }, { writerAlive }, { calls.add("stop") },
            { calls.add("restore") }, { pending.add(it) }, { fail("Unexpected timeout") })
        finish.run() // A playback-finished notification is not proof of thread exit.
        assertEquals(listOf("stop"), calls)
        assertEquals(1, pending.size)
        writerAlive = false
        pending.removeAt(0).run()
        assertEquals(listOf("stop", "restore"), calls)
    }

    @Test fun invalidatedEpochCannotStopOrRestore() {
        var owned = true
        var writerAlive = true
        var stops = 0
        val pending = mutableListOf<Runnable>()
        val finish = restoration({ owned }, { writerAlive }, { stops++ },
            { fail("Stale callback must not restore") }, { pending.add(it) }, { fail("Stale callback must not time out") })
        finish.run()
        owned = false // New preview, Stop, Pause, Destroy, or ordinary Start invalidates the token.
        writerAlive = false
        pending.removeAt(0).run()
        finish.run()
        assertEquals(1, stops)
        assertTrue(pending.isEmpty())
    }

    @Test fun alreadyCancelledCompletionHasZeroCallbacks() {
        val finish = restoration({ false }, { fail("Cancelled callback must not query writer"); true },
            { fail("Cancelled callback must not stop") }, { fail("Cancelled callback must not restore") },
            { fail("Cancelled callback must not retry") }, { fail("Cancelled callback must not time out") })
        finish.run()
    }

    @Test fun neverQuiescentWriterTimesOutOnceWithoutRestore() {
        var stops = 0
        var timeouts = 0
        var writerAlive = true
        val pending = mutableListOf<Runnable>()
        val finish = restoration({ true }, { writerAlive }, { stops++ },
            { fail("Live writer must never restore") }, { pending.add(it) }, { timeouts++ }, 3)
        finish.run()
        repeat(2) { pending.removeAt(0).run() }
        writerAlive = false
        finish.run()
        assertEquals(1, stops)
        assertEquals(1, timeouts)
        assertTrue(pending.isEmpty())
    }

    @Test fun failedIdleStartDefersRollbackUntilItsWriterExits() {
        var writerAlive = false
        val calls = mutableListOf<String>()
        val pending = mutableListOf<Runnable>()
        val finish = restoration({ true }, { writerAlive }, { calls.add("stop") },
            { calls.add("restore") }, { pending.add(it) }, { fail("Unexpected timeout") })
        assertFalse(startPreviewPlayback(false, { calls.add("prepare"); true },
            { calls.add("start"); writerAlive = true; false }, { finish.run() }))
        assertEquals(listOf("prepare", "start", "stop"), calls)
        writerAlive = false
        pending.removeAt(0).run()
        assertEquals(listOf("prepare", "start", "stop", "restore"), calls)
    }
}
