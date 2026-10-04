package com.vico.simulator.logging

import java.io.File
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.junit.Assert.*
import org.junit.Test

class SessionRecordingCoordinatorTest {
    private fun root() = Files.createTempDirectory("vico-coordinator-").toFile()
    private fun meta() = SessionRecorder.Metadata(100, 1700000000000, "apk:" + "a".repeat(64), "factory", "factory")
    private fun config() = arrayOf<Number?>(1L, 1, 2, 1, 3L, 0.0, 0.0, 0.0, 2000.0, 100.0, 3.0, 1)
    private fun gps() = arrayOf<Number?>(100L, 101L, 20.0, 1.0, 1, 1, 1, 1.0, 1)
    private fun waitFor(c: SessionRecordingCoordinator, condition: (SessionRecordingCoordinator.Snapshot) -> Boolean): SessionRecordingCoordinator.Snapshot {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        do { val status = c.snapshot(); if (condition(status)) return status; Thread.sleep(2) } while (System.nanoTime() < deadline)
        throw AssertionError("Timed out: ${c.snapshot()}")
    }
    @Test fun stopInvalidatesBlockedFactoryWithoutWaitingOrCreatingGhost() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1); val root = root()
        val c = SessionRecordingCoordinator(root)
        c.start("RX7", "hash", config()) { entered.countDown(); release.await(5, TimeUnit.SECONDS); meta() }
        assertTrue(entered.await(2, TimeUnit.SECONDS))
        repeat(5) { assertFalse(c.offerActive(SessionRecorder.Kind.GPS, 101, 1, 0, gps())) }
        assertEquals(5L, c.snapshot().startupGapRows)
        c.stop()
        assertEquals(SessionRecordingCoordinator.Phase.SAVING, c.snapshot().phase)
        assertEquals(1L, release.count) // stop returned without waiting for factory
        release.countDown()
        waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.COMPLETE }
        assertEquals(0, root.listFiles()!!.size)
        c.close(); waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.CLOSED }
    }
    @Test fun newestStartWinsAndFreezesConfigAndProfile() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1); val root = root()
        val factoryThread = AtomicReference<String>()
        val c = SessionRecordingCoordinator(root)
        c.start("old", "old", config()) { entered.countDown(); release.await(5, TimeUnit.SECONDS); meta() }
        assertTrue(entered.await(2, TimeUnit.SECONDS))
        val values = config()
        val newest = c.start("new", "newhash", values) { factoryThread.set(Thread.currentThread().name); meta() }
        values[5] = 99.0
        release.countDown()
        val ready = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.RECORDING }
        assertEquals(newest, ready.generation); assertEquals("vico-session-control", factoryThread.get())
        c.stop()
        val done = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.COMPLETE && it.lastCompleted != null }
        val text = File(done.lastCompleted!!.directory,"records.tsv").readText()
        assertTrue(text.contains("profile=new config=newhash")); assertFalse(text.contains("99.0"))
        val first = text.lineSequence().first { !it.startsWith('#') && it.isNotBlank() }
        assertTrue(first.startsWith("CONFIG\t")); assertEquals(1, root.listFiles()!!.size)
        c.close()
    }
    @Test fun startupGapPersistedAndCompletedFileRetainedForExport() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val c = SessionRecordingCoordinator(root()) { throw IllegalStateException("UI callback failure") }
        c.start("RX7", "hash", config()) { entered.countDown(); release.await(5, TimeUnit.SECONDS); meta() }
        assertTrue(entered.await(2, TimeUnit.SECONDS))
        repeat(7) { c.offerActive(SessionRecorder.Kind.GPS, 101, 1, 0, gps()) }
        release.countDown(); waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.RECORDING }
        c.stop()
        val done = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.COMPLETE && it.lastCompleted != null }
        assertEquals(7L, done.lastCompleted!!.status.preReadyDropped)
        assertTrue(File(done.lastCompleted!!.directory, "records.tsv").readText().contains("pre_ready_dropped=7"))
        val exported = done.lastCompleted!!.directory
        c.close(); waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.CLOSED }
        assertEquals(exported, c.snapshot().lastCompleted!!.directory)
        assertTrue(exported.isDirectory)
    }
    @Test fun invalidConfigNeverPublishesActive() {
        val c = SessionRecordingCoordinator(root())
        c.start("RX7", "hash", arrayOf(999)) { meta() }
        val failed = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.FAILED && it.lastCompleted != null }
        assertNull(failed.activeStatus); assertEquals("INITIAL_CONFIG_REJECTED", failed.failure)
        assertFalse(c.offerActive(SessionRecorder.Kind.GPS, 1, 1, 0, gps()))
        c.close()
    }
    @Test fun staleUnreadyObservationCannotWritePlaceholderAfterReadyRace() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val c = SessionRecordingCoordinator(root())
        c.start("RX7", "hash", config()) { entered.countDown(); release.await(5, TimeUnit.SECONDS); meta() }
        assertTrue(entered.await(2, TimeUnit.SECONDS))
        c.observeUnreadyRows(2)
        assertEquals(2L, c.snapshot().startupGapRows)
        release.countDown(); waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.RECORDING }
        // Adapter observed STARTING before readiness changed; accounting cannot enqueue a fake EVENT.
        c.observeUnreadyRows(3)
        assertEquals(3L, c.snapshot().noSessionRows)
        assertEquals(2L, c.snapshot().startupGapRows)
        c.stop()
        val done = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.COMPLETE && it.lastCompleted != null }
        val text = File(done.lastCompleted!!.directory, "records.tsv").readText()
        val rows = text.lineSequence().filter { !it.startsWith('#') && it.isNotBlank() }.toList()
        assertEquals(1, rows.size); assertTrue(rows.single().startsWith("CONFIG\t"))
        assertEquals(2L, done.lastCompleted!!.status.preReadyDropped)
        c.close()
    }
    @Test fun unreadyAccountingDoesNotWaitForCoordinatorLock() {
        val c = SessionRecordingCoordinator(root())
        val field = SessionRecordingCoordinator::class.java.getDeclaredField("lock").apply { isAccessible = true }
        val held = field.get(c) as java.util.concurrent.locks.ReentrantLock
        val returned = CountDownLatch(1)
        held.lock()
        try {
            val thread = Thread { c.observeUnreadyRows(7); returned.countDown() }.apply { start() }
            assertTrue(returned.await(1, TimeUnit.SECONDS)); thread.join()
        } finally { held.unlock() }
        assertEquals(7L, c.snapshot().coordinatorContentionDrops)
        assertEquals(0L, c.snapshot().noSessionRows)
        c.close()
    }
    @Test fun inSessionConfigAcceptancePrecedesDependentRowsAndGapsArePersisted() {
        val c = SessionRecordingCoordinator(root())
        c.start("RX7", "initialhash", config()) { meta() }
        waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.RECORDING }
        assertFalse(c.offerConfig(101, 1, 0, arrayOf(999)))
        c.observeConfigGap(2)
        val updated = config(); updated[0] = 2L; updated[5] = 0.5
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(2)
        while (!c.offerConfig(102, 1, 0, updated)) { if (System.nanoTime() > deadline) fail("CONFIG blocked"); Thread.sleep(1) }
        val model = arrayOfNulls<Number>(SessionRecorder.Kind.MODEL.fieldNames.size)
        model[1] = 1L; model[22] = 2L
        while (!c.offerActive(SessionRecorder.Kind.MODEL, 103, 1, 0, model)) { if (System.nanoTime() > deadline) fail("MODEL blocked"); Thread.sleep(1) }
        c.stop()
        val done = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.COMPLETE && it.lastCompleted != null }
        val text = File(done.lastCompleted!!.directory, "records.tsv").readText()
        val kinds = text.lineSequence().filter { !it.startsWith('#') && it.isNotBlank() }.map { it.substringBefore('\t') }.toList()
        assertEquals(listOf("CONFIG", "CONFIG", "MODEL"), kinds)
        assertTrue(text.contains("config=initialhash")); assertTrue(text.contains("config_gap_rows=2"))
        assertEquals(2L, done.lastCompleted!!.status.configGapRows)
        assertEquals(2L, done.configGapRows); c.close()
    }
    @Test fun rapidRequestsCoalesceWithoutUnboundedExecutorTasksOrStalePublication() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val factoryCalls = java.util.concurrent.atomic.AtomicInteger()
        val c = SessionRecordingCoordinator(root())
        c.start("blocked", "hash", config()) { factoryCalls.incrementAndGet(); entered.countDown(); release.await(5, TimeUnit.SECONDS); meta() }
        assertTrue(entered.await(2, TimeUnit.SECONDS))
        var latest = 0L
        repeat(1000) { i -> latest = c.start("p$i", "hash", config()) { factoryCalls.incrementAndGet(); meta() } }
        release.countDown()
        val ready = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.RECORDING }
        assertEquals(latest, ready.generation); assertEquals(2, factoryCalls.get())
        c.stop(); val done = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.COMPLETE && it.lastCompleted != null }
        assertTrue(File(done.lastCompleted!!.directory, "records.tsv").readText().contains("profile=p999"))
        c.close()
    }
    @Test fun metadataFailureIsExplicitAndDoesNotCreateSession() {
        val root = root(); val c = SessionRecordingCoordinator(root)
        c.start("RX7", "hash", config()) { throw java.io.IOException("hash lookup failed") }
        val status = waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.FAILED }
        assertEquals("SESSION_INITIALIZATION_FAILED", status.failure); assertNull(status.activeStatus)
        assertEquals(0, root.listFiles()!!.size)
        c.close()
    }
    @Test fun closeWhileInitializingNeverReopensAndRejectsRestart() {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val c = SessionRecordingCoordinator(root())
        c.start("RX7", "hash", config()) { entered.countDown(); release.await(5, TimeUnit.SECONDS); meta() }
        assertTrue(entered.await(2, TimeUnit.SECONDS))
        c.close(); release.countDown(); waitFor(c) { it.phase == SessionRecordingCoordinator.Phase.CLOSED }
        try { c.start("RX7", "hash", config()) { meta() }; fail("closed") } catch (_: IllegalStateException) { }
        assertNull(c.snapshot().activeStatus)
    }
}
