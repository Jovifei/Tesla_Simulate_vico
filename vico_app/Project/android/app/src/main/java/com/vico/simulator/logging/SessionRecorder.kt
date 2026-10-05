package com.vico.simulator.logging

import java.io.File
import java.io.FileOutputStream
import java.util.ArrayDeque
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.locks.ReentrantLock

/** Isolated JVM candidate. Start on a control executor, never on the audio or UI thread.
 * No networking, deletion, coordinates, microphone samples, arbitrary event text, or Android dependency.
 * offer() is best-effort and never waits for the queue lock. It still allocates a bounded snapshot;
 * audio render callbacks must publish primitive counters to a lower-rate collector instead.
 */
class SessionRecorder private constructor(
    val directory: File, private val limits: Limits, private val header: String,
) {
    data class Limits(val queueRecords: Int = 512, val sessionBytes: Long = 32L * 1024 * 1024,
                      val retainedSessions: Int = 20, val retainedBytes: Long = 256L * 1024 * 1024) {
        init { require(queueRecords in 1..8192 && sessionBytes >= 8192 && retainedSessions in 1..1000 && retainedBytes >= sessionBytes) }
    }
    data class Metadata(val monotonicAnchorNs: Long, val wallAnchorMs: Long,
                        val buildId: String, val profileId: String, val configHash: String,
                        val androidApi: Int? = null, val deviceModel: String? = null) {
        init {
            require(monotonicAnchorNs >= 0 && wallAnchorMs > 0)
            require(androidApi == null || androidApi in 1..1000)
            require(deviceModel == null || deviceModel.matches(Regex("[A-Za-z0-9_.:-]{1,96}")))
            for (s in listOf(buildId, profileId, configHash)) require(s.matches(Regex("[A-Za-z0-9_.:-]{1,96}")))
        }
    }
    enum class Kind(val fields: String) {
        CONFIG("config_revision_id,unit_code,mount_axis_code,mount_confirmed,calibration_revision_id,bias_x_mps2,bias_y_mps2,bias_z_mps2,gps_fresh_ms,imu_fresh_ms,gps_uncertainty_threshold_mps,display_unit_code"),
        CONTROL("input_session_id,control_frame_id,publish_ns,valid_until_ns,gps_sample_ns,imu_sample_ns,raw_speed_mps,selected_speed_mps,selected_accel_mps2,source_mode,drive_mode,gps_quality,imu_quality,speed_usable,acceleration_usable,config_revision_id"),
        GPS("source_ns,receive_ns,raw_speed_mps,accuracy_mps,accuracy_status,valid,provider_code,age_ms,has_speed"),
        IMU("source_ns,receive_ns,raw_x_mps2,raw_y_mps2,raw_z_mps2,bias_x_mps2,bias_y_mps2,bias_z_mps2,longitudinal_mps2,filtered_mps2,mapping_code,valid,age_ms,config_revision_id"),
        MODEL("input_session_id,control_frame_id,publish_ns,consume_ns,valid_until_ns,raw_speed_mps,selected_speed_mps,model_speed_mps,ui_speed_kmh,accel_mps2,rpm,gear,load,throttle,source_mode,drive_mode,gps_quality,imu_quality,speed_usable,acceleration_usable,afterfire_cause,afterfire_source_id,config_revision_id"),
        UI_ACK("publish_ns,consume_ns,dispatch_ns,received_render_ack_ns,display_speed_kmh,display_unit_code,display_value"),
        EVENT("event_code,cause_code,event_id,source_id,control_frame_id,rpm,gear,throttle,load,requested_ns,consumed_ns,config_revision_id"),
        AUDIO("audio_block_id,sample_rate_hz,buffer_frames,underrun_count,render_duration_ns,write_duration_ns,write_result_frames,clip_count,peak,output_route_code,blocks_in_window");
        val fieldNames = fields.split(',')
        val exactIndices = fieldNames.indices.filter { fieldNames[it].endsWith("_ns") || fieldNames[it].endsWith("_id") || fieldNames[it] == "blocks_in_window" }
    }
    enum class State { RECORDING, STOPPING, COMPLETE, CAPACITY, IO_FAILED }
    data class Status(val state: State, val accepted: Long, val written: Long, val queueDropped: Long,
                      val rejected: Long, val unwritten: Long, val bytes: Long, val preReadyDropped: Long = 0, val configGapRows: Long = 0)
    private val lock = ReentrantLock()
    private val accepted = AtomicLong(); private val written = AtomicLong()
    private val dropped = AtomicLong(); private val rejected = AtomicLong()
    private val unwritten = AtomicLong(); private val bytes = AtomicLong()
    private val preReadyDropped = AtomicLong()
    private val configGapRows = AtomicLong()
    @Volatile private var state = State.RECORDING
    @Volatile private var stopping = false
    private val done = CountDownLatch(1)
    private val worker = Thread({ writeLoop() }, "vico-session-writer").apply { isDaemon = true }

    /** Use Long for exact nanoseconds and counters, Double for physical quantities, null for unavailable.
     * Values must already follow Kind.fields; no strings or non-finite doubles enter the persisted file.
     * Returns false on invalid values, overload, stopped recorder, or contention; counters explain loss.
     */
    fun offer(kind: Kind, elapsedNs: Long, frameId: Long, inputEpoch: Long, values: Array<out Number?>): Boolean {
        if (elapsedNs < 0 || frameId < 0 || inputEpoch < 0 || values.size != kind.fieldNames.size ||
            values.any { it != null && it !is Long && it !is Int && it !is Double || it is Double && !it.isFinite() }) {
            rejected.incrementAndGet(); return false
        }
        if (kind.exactIndices.any { i -> values[i] != null && values[i] !is Long && values[i] !is Int }) { rejected.incrementAndGet(); return false }
        if (kind.exactIndices.any { i -> (values[i]?.toLong() ?: 0L) < 0L } ||
            kind.fieldNames.indices.any { i ->
                val value = values[i]
                val domain = codeDomains[kind.fieldNames[i]]
                value != null && domain != null &&
                    ((value !is Int && value !is Long) || value.toLong() !in domain)
            }) { rejected.incrementAndGet(); return false }
        // Formatting belongs to writer; retain numeric types exactly, not Double-converted timestamps.
        return enqueue(kind, elapsedNs, frameId, inputEpoch, values)
    }
    private data class NumericRecord(val kind: Kind, val elapsedNs: Long, val frameId: Long,
                                     val inputEpoch: Long, val values: Array<out Number?>)
    private val numericQueue = ArrayDeque<NumericRecord>()
    private fun enqueue(kind: Kind, elapsedNs: Long, frameId: Long, inputEpoch: Long, values: Array<out Number?>): Boolean {
        if (stopping) { rejected.incrementAndGet(); return false }
        val snapshot = values.copyOf()
        if (!lock.tryLock()) { dropped.incrementAndGet(); return false }
        try {
            if (stopping) { rejected.incrementAndGet(); return false }
            if (numericQueue.size >= limits.queueRecords) { dropped.incrementAndGet(); return false }
            numericQueue.addLast(NumericRecord(kind, elapsedNs, frameId, inputEpoch, snapshot))
            accepted.incrementAndGet()
            return true
        } finally { lock.unlock() }
    }
    /** No IO or writer join; briefly acquires queue lock. awaitClosed is for control executors/tests only. */
    fun stop() {
        lock.lock()
        try { stopping = true; if (state == State.RECORDING) state = State.STOPPING } finally { lock.unlock() }
    }
    fun awaitClosed(timeoutMs: Long): Boolean = done.await(timeoutMs, TimeUnit.MILLISECONDS)
    internal fun notePreReadyDropped(count: Long) { require(count >= 0); preReadyDropped.addAndGet(count) }
    internal fun noteConfigGap(count: Long) { require(count >= 0); configGapRows.addAndGet(count) }
    fun status() = Status(state, accepted.get(), written.get(), dropped.get(), rejected.get(), unwritten.get(), bytes.get(), preReadyDropped.get(), configGapRows.get())
    private fun writeLoop() {
        val partial = File(directory, "records.partial.tsv")
        try {
            FileOutputStream(partial).use { out ->
                fun write(line: String) { val data = line.toByteArray(Charsets.UTF_8); out.write(data); bytes.addAndGet(data.size.toLong()) }
                write(header)
                var lastFlush = System.nanoTime()
                while (true) {
                    val record: NumericRecord?
                    val finished: Boolean
                    lock.lock()
                    try { record = numericQueue.pollFirst(); finished = stopping && record == null } finally { lock.unlock() }
                    if (finished) break
                    if (record == null) {
                        if (System.nanoTime() - lastFlush >= TimeUnit.SECONDS.toNanos(1)) { out.fd.sync(); lastFlush = System.nanoTime() }
                        Thread.sleep(10); continue
                    }
                    val line = "${record.kind}\t${record.elapsedNs}\t${record.frameId}\t${record.inputEpoch}\t" + record.values.joinToString("\t") { it?.toString() ?: "" } + "\n"
                    val data = line.toByteArray(Charsets.UTF_8)
                    if (bytes.get() + data.size + 1024 > limits.sessionBytes) {
                        lock.lock()
                        try { stopping = true; state = State.CAPACITY; unwritten.addAndGet(1L + numericQueue.size); numericQueue.clear() } finally { lock.unlock() }
                        break
                    }
                    out.write(data); bytes.addAndGet(data.size.toLong()); written.incrementAndGet()
                    if (System.nanoTime() - lastFlush >= TimeUnit.SECONDS.toNanos(1)) { out.fd.sync(); lastFlush = System.nanoTime() }
                }
                write("# end state=${if (state == State.STOPPING) State.COMPLETE else state} accepted=${accepted.get()} written=${written.get()} queue_dropped=${dropped.get()} rejected=${rejected.get()} unwritten=${unwritten.get()} pre_ready_dropped=${preReadyDropped.get()} config_gap_rows=${configGapRows.get()}\n")
                out.fd.sync()
            }
            if (!partial.renameTo(File(directory, "records.tsv"))) throw java.io.IOException("finalize failed")
            if (state == State.STOPPING) state = State.COMPLETE
        } catch (_: Exception) {
            lock.lock()
            try { stopping = true; state = State.IO_FAILED; unwritten.set(accepted.get() - written.get()); numericQueue.clear() } finally { lock.unlock() }
        } finally {
            synchronized(Companion) { reservations.remove(directory.canonicalPath) }
            done.countDown()
        }
    }
    companion object {
        const val SCHEMA_VERSION = 2
        // Stable wire maps: never derive values from an enum ordinal.
        val ENUM_MAPS: Map<String, String> = linkedMapOf(
            "display_unit_code" to "0:UNKNOWN,1:KMH,2:MPH",
            "unit_code" to "1:SI_MPS_MPS2_WITH_EXPLICIT_KMH_FIELDS",
            "mount_axis_code" to "0:UNKNOWN,1:POS_X,2:POS_Y,3:POS_Z,4:NEG_X,5:NEG_Y,6:NEG_Z",
            "source_mode" to "0:UNSPECIFIED,1:REAL,2:DEMO,3:PREVIEW,4:QUALIFICATION",
            "drive_mode" to "0:UNKNOWN,1:LIVE,2:PREVIEW,3:REFERENCE_BYPASS",
            "gps_quality" to "0:UNKNOWN,1:FRESH,2:UNVERIFIED,3:STALE,4:LOW_QUALITY,5:UNAVAILABLE,6:SYNTHETIC",
            "imu_quality" to "0:UNKNOWN,1:FRESH,2:UNCONFIRMED_FRAME,3:UNAVAILABLE,4:SYNTHETIC",
            "accuracy_status" to "0:UNKNOWN,1:AVAILABLE,2:NOT_REPORTED,3:UNSUPPORTED_API,4:INVALID",
            "provider_code" to "0:UNKNOWN,1:GPS,2:NETWORK,3:FUSED,4:PASSIVE,5:SYNTHETIC,6:OTHER",
            "event_code" to "0:UNKNOWN,1:SESSION_START,2:SESSION_STOP,3:SHIFT,4:AFTERFIRE,5:WATCHDOG_TIMEOUT,6:PROFILE_CHANGE,7:MODE_CHANGE,8:CALIBRATION_CHANGE,9:AUDIO_ROUTE_CHANGE,10:START_FAILURE",
            "cause_code" to "0:NONE,1:RELEASE,2:SHIFT,3:INPUT_EXPIRED,4:INPUT_INVALID,5:USER_ACTION,6:LIFECYCLE,7:ERROR",
            "afterfire_cause" to "0:NONE,1:RELEASE,2:SHIFT",
            "output_route_code" to "0:UNKNOWN,1:SPEAKER,2:WIRED,3:BLUETOOTH,4:USB,5:OTHER",
            "mapping_code" to "0:UNKNOWN,1:POS_X,2:POS_Y,3:POS_Z,4:NEG_X,5:NEG_Y,6:NEG_Z"
        )
        private val codeDomains = ENUM_MAPS.mapValues { (_, tokens) ->
            tokens.split(',').map { it.substringBefore(':').toLong() }.toSet()
        } + setOf("mount_confirmed", "valid", "has_speed", "speed_usable", "acceleration_usable").associateWith { setOf(0L, 1L) }
        private val reservations = HashMap<String, Long>()
        /** One process-wide admission lock. Reserves the full maximum session size for active sessions.
         * All directories under root are owned logs; this never removes existing user files.
         */
        @Synchronized fun start(root: File, metadata: Metadata, limits: Limits = Limits()): SessionRecorder {
            require(root.isDirectory || root.mkdirs()) { "Cannot create log root" }
            val entries = root.listFiles() ?: throw java.io.IOException("Cannot list log root")
            require(entries.size < limits.retainedSessions) { "Log session count full; export/manage logs" }
            val reserved = entries.sumOf { entry ->
                reservations[entry.canonicalPath] ?: entry.walkTopDown().filter { it.isFile }.sumOf { it.length() }
            }
            require(reserved <= limits.retainedBytes - limits.sessionBytes) { "Log storage full; export/manage logs" }
            val directory = File(root, "session-${UUID.randomUUID()}")
            check(directory.mkdir()) { "Cannot create session" }
            // Create marker before another admission, so an active empty session is reserved too.
            check(File(directory, "records.partial.tsv").createNewFile())
            val header = buildString {
                append("# vico_session_schema=$SCHEMA_VERSION monotonic_clock=android_elapsedRealtimeNanos ns_encoding=decimal_integer\n")
                append("# anchor_ns=${metadata.monotonicAnchorNs} anchor_unix_ms=${metadata.wallAnchorMs} build=${metadata.buildId} profile=${metadata.profileId} config=${metadata.configHash} android_api=${metadata.androidApi ?: "unknown"} device_model=${metadata.deviceModel ?: "unknown"}\n")
                append("# row=kind,elapsed_ns,frame_id,input_epoch,payload; unavailable=empty; booleans=0/1\n")
                ENUM_MAPS.forEach { (name, codes) -> append("# enum.$name=$codes\n") }
                Kind.values().forEach { append("# ${it.name}=${it.fields}\n") }
            }
            reservations[directory.canonicalPath] = limits.sessionBytes
            return SessionRecorder(directory, limits, header).also { it.worker.start() }
        }
    }
}
