package com.vico.simulator.logging

import java.io.File
import java.util.concurrent.ScheduledThreadPoolExecutor
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/** Single app owner; factories run on a bounded/coalescing control worker, never UI/audio.
 * Factories must not wait for UI. Callbacks are notifications: caller marshals to UI and may poll snapshot.
 * Profile/soundbank change means a new session; calibration CONFIG can change in FIFO order. No deletion and no Android dependencies.
 */
class SessionRecordingCoordinator(
    private val root: File,
    private val limits: SessionRecorder.Limits = SessionRecorder.Limits(),
    private val onStatus: (Snapshot) -> Unit = {},
) {
    enum class Phase { IDLE, STARTING, RECORDING, SAVING, COMPLETE, CAPACITY, FAILED, CLOSED }
    data class Completed(val directory: File, val generation: Long, val status: SessionRecorder.Status)
    data class Snapshot(val generation: Long, val phase: Phase, val startupGapRows: Long,
                        val noSessionRows: Long, val coordinatorContentionDrops: Long,
                        val activeStatus: SessionRecorder.Status?, val lastCompleted: Completed?, val failure: String?,
                        val configGapRows: Long = 0)
    private data class Request(val generation: Long, val profile: String, val hash: String,
                               val config: Array<out Number?>, val factory: () -> SessionRecorder.Metadata)
    private data class Owned(val generation: Long, val recorder: SessionRecorder, val initialConfigRevision: Long? = null,
                             var startRequestedNs: Long? = null, var startRecorded: Boolean = false)
    private val lock = ReentrantLock()
    private val executor = ScheduledThreadPoolExecutor(1) { task -> Thread(task, "vico-session-control").apply { isDaemon = true } }
    private var generation = 0L
    private var phase = Phase.IDLE
    private var pending: Request? = null
    @Volatile private var active: Owned? = null
    private val retiring = ArrayList<Owned>()
    private var scheduled = false
    private var closed = false
    private var gap = 0L
    private var idleRows = 0L
    private val contentionDrops = AtomicLong()
    private val configGapRows = AtomicLong()
    private var lastCompleted: Completed? = null
    private var failure: String? = null
    private var cancelledStartGeneration = -1L

    /** Copies numeric config now; Metadata factory must capture only immutable request context.
     * build hash/clock/platform lookup happens in factory. Returned profile/hash are overridden by frozen args.
     */
    fun start(profileId: String, configHash: String, configValues: Array<out Number?>,
              metadataFactory: () -> SessionRecorder.Metadata): Long {
        val copy = configValues.copyOf()
        val id = lock.withLock {
            check(!closed) { "Coordinator closed" }
            generation++
            retireActiveLocked()
            gap = 0; failure = null; phase = Phase.STARTING
            pending = Request(generation, profileId, configHash, copy, metadataFactory)
            scheduleLocked()
            generation
        }
        notifyStatus(); return id
    }
    /** No IO, no join; recorder stop takes only its short queue lock. */
    fun stop() {
        lock.withLock {
            generation++; pending = null; retireActiveLocked()
            phase = if (retiring.isNotEmpty() || scheduled) Phase.SAVING else if (closed) Phase.CLOSED else Phase.COMPLETE
            scheduleLocked()
        }
        notifyStatus()
    }
    fun close() {
        lock.withLock { closed = true }
        stop()
    }
    fun offerActive(kind: SessionRecorder.Kind, elapsedNs: Long, frameId: Long, inputEpoch: Long,
                    values: Array<out Number?>): Boolean {
        if (!lock.tryLock()) { contentionDrops.incrementAndGet(); return false }
        val recorder: SessionRecorder?
        try {
            val owned = active
            if (owned?.startRequestedNs != null && !owned.startRecorded) {
                offerSessionStartLocked(owned)
                if (!owned.startRecorded) { idleRows++; return false }
            }
            recorder = owned?.recorder
            if (recorder == null) { if (phase == Phase.STARTING) gap++ else idleRows++ }
        } finally { lock.unlock() }
        return recorder?.offer(kind, elapsedNs, frameId, inputEpoch, values) ?: false
    }
    /** SESSION_START means a successful sound-test request observed with recording READY, not audible output.
     * Idempotent for this exact generation; a background pump retries transient recorder contention/fullness.
     * False means not queued: the main collector may retry while the same request is still valid.
     */
    fun requestSessionStart(expectedGeneration: Long, elapsedNs: Long): Boolean {
        if (elapsedNs < 0 || !lock.tryLock()) return false
        try {
            val owned = active ?: return false
            if (closed || phase != Phase.RECORDING || generation != expectedGeneration ||
                owned.generation != expectedGeneration || cancelledStartGeneration == expectedGeneration) return false
            if (!owned.startRecorded && owned.startRequestedNs == null) owned.startRequestedNs = elapsedNs
            return true
        } finally { lock.unlock() }
    }
    /** No IO or waiting for worker completion; same short state lock as stop/snapshot. */
    fun cancelSessionStart(expectedGeneration: Long) {
        lock.withLock {
            if (generation != expectedGeneration) return
            val owned = active
            // Once READY was confirmed, that historical start remains true even if stop arrives
            // before disk enqueue. Only cancel an unconfirmed/future late READY callback.
            if (owned?.startRequestedNs == null && owned?.startRecorded != true)
                cancelledStartGeneration = expectedGeneration
        }
    }
    private fun offerSessionStartLocked(owned: Owned) {
        val ns = owned.startRequestedNs ?: return
        if (owned.startRecorded || cancelledStartGeneration == owned.generation) return
        // Event id zero is reserved for this one coordinator-owned lifecycle marker;
        // ordinary adapter events start at one. Initial CONFIG revision identifies session startup.
        if (owned.recorder.offer(SessionRecorder.Kind.EVENT, ns, 0, 0,
                arrayOf<Number?>(1, 0, 0L, null, 0L, null, null, null, null, ns, null, owned.initialConfigRevision))) {
            owned.startRecorded = true
            owned.startRequestedNs = null
        }
    }
    /** Count rows skipped after an unready observation without ever enqueuing a placeholder.
     * If READY won the race, count as no-session/skipped rows, not as a real event.
     */
    fun observeUnreadyRows(count: Long = 1) {
        require(count >= 0)
        if (count == 0L) return
        if (!lock.tryLock()) { contentionDrops.addAndGet(count); return }
        try { if (phase == Phase.STARTING) gap += count else idleRows += count }
        finally { lock.unlock() }
    }
    /** Caller must serialize CONFIG acceptance and subsequent dependent rows on the same producer.
     * Advance revision only on true; skip dependent rows and observeConfigGap on false, retry later.
     */
    fun offerConfig(elapsedNs: Long, frameId: Long, inputEpoch: Long, values: Array<out Number?>): Boolean =
        offerActive(SessionRecorder.Kind.CONFIG, elapsedNs, frameId, inputEpoch, values)
    fun observeConfigGap(skippedRows: Long = 1) {
        require(skippedRows >= 0)
        configGapRows.addAndGet(skippedRows)
        active?.recorder?.noteConfigGap(skippedRows)
    }
    fun snapshot(): Snapshot = lock.withLock {
        Snapshot(generation, phase, gap, idleRows, contentionDrops.get(), active?.recorder?.status(), lastCompleted, failure, configGapRows.get())
    }
    private fun notifyStatus() { try { onStatus(snapshot()) } catch (_: Exception) { /* UI observer cannot break recording. */ } }
    private fun retireActiveLocked() {
        active?.let {
            if (it.startRequestedNs == null || it.startRecorded) it.recorder.stop()
            retiring.add(it)
        }; active = null
    }
    private fun scheduleLocked() {
        if (!scheduled && !executor.isShutdown) { scheduled = true; executor.execute { pump() } }
    }
    private fun initialize(request: Request) {
        var recorder: SessionRecorder? = null
        try {
            if (lock.withLock { closed || request.generation != generation }) return
            val metadata = request.factory().copy(profileId = request.profile, configHash = request.hash)
            if (lock.withLock { closed || request.generation != generation }) return
            recorder = SessionRecorder.start(root, metadata, limits)
            // No producers yet, retry only bounded transient queue-lock contention.
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(1)
            var configured = false
            while (!configured && System.nanoTime() < deadline) {
                if (lock.withLock { closed || request.generation != generation }) break
                val rejectedBefore = recorder.status().rejected
                configured = recorder.offer(SessionRecorder.Kind.CONFIG, metadata.monotonicAnchorNs, 0, 0, request.config)
                if (!configured && recorder.status().rejected > rejectedBefore) break
                if (!configured) Thread.sleep(1)
            }
            val initialized = recorder
            lock.withLock {
                if (request.generation == generation && !closed && configured && initialized.status().state == SessionRecorder.State.RECORDING) {
                    initialized.notePreReadyDropped(gap)
                    active = Owned(request.generation, initialized, request.config[0]?.toLong()); phase = Phase.RECORDING
                    recorder = null
                } else if (request.generation == generation && !closed) {
                    phase = Phase.FAILED; failure = "INITIAL_CONFIG_REJECTED"
                }
            }
        } catch (_: Exception) {
            lock.withLock { if (request.generation == generation && !closed) { phase = Phase.FAILED; failure = "SESSION_INITIALIZATION_FAILED" } }
        } finally {
            recorder?.let { r -> r.stop(); lock.withLock { retiring.add(Owned(request.generation, r)) } }
        }
    }
    private fun pump() {
        val request = lock.withLock { val r = pending; pending = null; r }
        request?.let { initialize(it) }
        lock.withLock {
            active?.let { owned ->
                when (owned.recorder.status().state) {
                    SessionRecorder.State.CAPACITY -> { phase = Phase.CAPACITY; retireActiveLocked() }
                    SessionRecorder.State.IO_FAILED -> { phase = Phase.FAILED; failure = "SESSION_IO_FAILED"; retireActiveLocked() }
                    SessionRecorder.State.RECORDING -> offerSessionStartLocked(owned)
                    else -> Unit
                }
            }
            val iterator = retiring.iterator()
            while (iterator.hasNext()) {
                val owned = iterator.next()
                if (owned.startRequestedNs != null && !owned.startRecorded) {
                    if (owned.recorder.status().state == SessionRecorder.State.RECORDING) offerSessionStartLocked(owned)
                    if (owned.startRecorded || owned.recorder.status().state != SessionRecorder.State.RECORDING) owned.recorder.stop()
                }
                if (owned.recorder.awaitClosed(0)) {
                    val result = Completed(owned.recorder.directory, owned.generation, owned.recorder.status())
                    if ((lastCompleted?.generation ?: -1) <= owned.generation) lastCompleted = result
                    iterator.remove()
                    if (phase == Phase.SAVING && pending == null && active == null && retiring.isEmpty())
                        phase = if (closed) Phase.CLOSED else when (result.status.state) {
                            SessionRecorder.State.IO_FAILED -> { failure = "SESSION_IO_FAILED"; Phase.FAILED }
                            SessionRecorder.State.CAPACITY -> Phase.CAPACITY
                            else -> Phase.COMPLETE
                        }
                }
            }
            if (phase == Phase.SAVING && active == null && pending == null && retiring.isEmpty()) phase = if (closed) Phase.CLOSED else Phase.COMPLETE
            if (closed && pending == null && active == null && retiring.isEmpty()) { phase = Phase.CLOSED; executor.shutdown(); scheduled = false }
            else if (pending != null || active != null || retiring.isNotEmpty()) executor.schedule({ pump() }, 20, TimeUnit.MILLISECONDS)
            else scheduled = false
        }
        notifyStatus()
    }
}
