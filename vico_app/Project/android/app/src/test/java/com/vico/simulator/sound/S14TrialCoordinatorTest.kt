package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test

class S14TrialCoordinatorTest {
    @Test fun stopped_preview_cannot_own_a_new_trial() {
        val epoch = S14CallbackEpoch()
        val preview = epoch.next()
        epoch.next() // Stop
        val reference = epoch.next()
        assertFalse(epoch.owns(preview))
        assertTrue(epoch.owns(reference))
    }
    @Test fun old_completion_cannot_change_new_trial() {
        val c = S14TrialCoordinator()
        val a = c.begin("R")
        c.fail(a, "start failed")
        val b = c.begin("M")
        assertFalse(c.advance(a, S14TrialCoordinator.State.FINISHED))
        assertEquals(b, c.ticket)
        assertEquals(S14TrialCoordinator.State.LOADING, c.state)
    }
    @Test(expected = IllegalStateException::class)
    fun duplicate_start_is_rejected() {
        val c = S14TrialCoordinator(); c.begin("R"); c.begin("M")
    }
    @Test fun failed_loading_can_be_retried() {
        val c = S14TrialCoordinator(); val a = c.begin("R")
        c.fail(a, "bad source")
        assertFalse(c.busy)
        assertNotEquals(a.id, c.begin("M").id)
    }
    @Test fun cannot_skip_loading_and_export_stages() {
        val c = S14TrialCoordinator(); val t = c.begin("R")
        assertFalse(c.advance(t, S14TrialCoordinator.State.FINISHED))
        assertTrue(c.advance(t, S14TrialCoordinator.State.READY))
        assertTrue(c.advance(t, S14TrialCoordinator.State.PLAYING))
        assertTrue(c.advance(t, S14TrialCoordinator.State.EXPORTING))
        assertTrue(c.busy)
        assertTrue(c.advance(t, S14TrialCoordinator.State.FINISHED))
        assertFalse(c.busy)
    }

    @Test fun late_failure_cannot_reopen_a_finished_trial() {
        val c = S14TrialCoordinator(); val t = c.begin("R")
        c.advance(t, S14TrialCoordinator.State.READY)
        c.advance(t, S14TrialCoordinator.State.PLAYING)
        c.advance(t, S14TrialCoordinator.State.EXPORTING)
        c.advance(t, S14TrialCoordinator.State.FINISHED)
        c.fail(t, "late callback")
        assertEquals(S14TrialCoordinator.State.FINISHED, c.state)
        assertNull(c.error)
    }

    @Test fun cancelled_loading_cannot_complete_after_retry() {
        val c = S14TrialCoordinator(); val a = c.begin("R")
        c.abort(a, "USER_STOP")
        assertFalse(c.busy)
        val b = c.begin("M")
        assertFalse(c.advance(a, S14TrialCoordinator.State.READY))
        assertEquals(b, c.ticket)
        assertEquals(S14TrialCoordinator.State.LOADING, c.state)
    }
}
