package com.vico.simulator.sound

import com.vico.simulator.vehicle.CurrentVehicleCatalog
import org.junit.Assert.*
import org.junit.Test

/** Runs source-extracted production Activity entry points, with controlled UI/writer ports. */
class PreviewActivityTest {
    private val original = CurrentVehicleCatalog.defaultKey
    private val preview = "ferrari_458"
    private val replacement = "lfa"

    private fun failedPreviewWithExitedWriter(activity: HeadlessMainActivity): Runnable {
        activity.previewVehicle(preview)
        val restore = activity.previewRestore!!
        assertTrue(activity.audioRunning)
        activity.audioEngine.failAudio() // Execute the production onAudioFailure callback.
        assertFalse(activity.audioRunning)
        assertTrue(activity.audioEngine.writerAlive) // Failure callback precedes writer exit.
        activity.audioEngine.writerAlive = false
        assertSame(restore, activity.previewRestore)
        return restore
    }

    @Test fun successfulS13InvalidatesOldPreviewEvenIfItsTaskWasAlreadyDispatched() {
        val activity = HeadlessMainActivity()
        val restore = failedPreviewWithExitedWriter(activity)
        activity.audioEngine.beforeReviewStart = {
            assertSame("Cancel only after successful engine start", restore, activity.previewRestore)
        }
        activity.beginS13(replacement)
        assertTrue(activity.audioRunning)
        val reviewOwner = activity.audioEngine.owner
        val stops = activity.audioEngine.stops
        restore.run() // Simulate an already-dequeued old Runnable, bypassing Handler removal.
        assertEquals("Old Preview must not stop a newly accepted S13 writer", stops, activity.audioEngine.stops)
        assertTrue(activity.audioEngine.writerAlive)
        assertEquals(reviewOwner, activity.audioEngine.owner)
        assertEquals(replacement, activity.activeVehicleKey)
        assertEquals(replacement, activity.audioEngine.vehicle)
        assertNull(activity.previewRestore)
        assertFalse(activity.handler.pending.any { it.task === restore })
        assertTrue(activity.events.indexOf("handler.remove") > activity.events.indexOf("engine.review.accepted"))
        assertTrue(activity.ui.last().s13Active)
        assertNull(activity.ui.last().pendingRestore)
    }

    @Test fun failedS13KeepsPendingPreviewAndRestoresOriginalBankAndCharacter() {
        val activity = HeadlessMainActivity()
        val restore = failedPreviewWithExitedWriter(activity)
        activity.audioEngine.reviewStartSucceeds = false
        activity.beginS13(replacement)
        assertFalse(activity.audioRunning)
        assertFalse(activity.s13ReviewActive)
        assertNull(activity.s13ReviewVehicleKey)
        assertSame("Rejected S13 must keep original rollback", restore, activity.previewRestore)
        assertTrue(activity.handler.pending.any { it.task === restore })
        assertFalse(activity.events.contains("handler.remove"))
        activity.handler.run(restore)
        assertEquals(original, activity.activeVehicleKey)
        assertEquals(original, activity.audioEngine.vehicle)
        assertEquals(SoundProfile.SOFT, activity.audioEngine.profile)
        assertNull(activity.previewRestore)
    }

    @Test fun secondPreviewWhileRestorePendingRejectsWithoutAnyCancellationOrLogMutation() {
        val activity = HeadlessMainActivity()
        val restore = failedPreviewWithExitedWriter(activity)
        activity.testLog.requested = true
        val eventsBefore = activity.events.toList()
        val uiBefore = activity.ui.toList()
        val ownerBefore = activity.audioEngine.owner
        val pendingBefore = activity.handler.pending.toList()
        val selectedBefore = activity.vehicleState.selectedKey
        activity.previewVehicle(replacement)
        assertSame("Pending original restore must survive second Preview", restore, activity.previewRestore)
        assertEquals(eventsBefore, activity.events)
        assertEquals(uiBefore, activity.ui)
        assertEquals(pendingBefore, activity.handler.pending)
        assertEquals(ownerBefore, activity.audioEngine.owner)
        assertEquals(selectedBefore, activity.vehicleState.selectedKey)
        assertEquals(preview, activity.activeVehicleKey)
        assertEquals(preview, activity.audioEngine.vehicle)
        assertTrue(activity.testLog.requested)
        assertTrue(activity.audioEngine.diagnosticLoggingEnabled)
        assertTrue("Explain that prior Preview restoration is pending", activity.toasts.last().contains("恢复"))
        activity.handler.run(restore)
        assertEquals(original, activity.audioEngine.vehicle) // Also proves old epoch stayed valid.
    }

    @Test fun previewAfterPriorRestoreUsesOriginalBaselineAgain() {
        val activity = HeadlessMainActivity()
        val restoreB = failedPreviewWithExitedWriter(activity)
        activity.previewVehicle(replacement) // C rejected until B has restored A.
        activity.handler.run(restoreB)
        assertEquals(original, activity.activeVehicleKey)
        activity.previewVehicle(replacement)
        assertEquals(replacement, activity.activeVehicleKey)
        val restoreC = activity.previewRestore!!
        assertNotSame(restoreB, restoreC)
        activity.handler.run(restoreC)
        assertEquals(original, activity.activeVehicleKey)
        assertEquals(original, activity.audioEngine.vehicle)
        assertEquals(SoundProfile.SOFT, activity.audioEngine.profile)
        assertNull(activity.previewRestore)
    }

    @Test fun ordinaryPreviewCompletionRestoresOnceAndStaleFailureCannotStopS13() {
        val activity = HeadlessMainActivity()
        activity.previewVehicle(preview)
        val oldOwner = activity.audioEngine.owner
        val restore = activity.previewRestore!!
        activity.handler.run(restore)
        val stops = activity.audioEngine.stops
        restore.run()
        assertEquals(stops, activity.audioEngine.stops)
        assertEquals(original, activity.activeVehicleKey)
        activity.beginS13(replacement)
        activity.audioEngine.onAudioFailure!!(oldOwner, "stale failure")
        assertTrue(activity.audioRunning)
        assertTrue(activity.audioEngine.writerAlive)
        assertEquals(replacement, activity.vehicleState.playingKey)
    }
}
