package com.vico.simulator.logging

import java.io.File
import java.nio.file.Files
import org.junit.Assert.*
import org.junit.Test

class SessionRecorderTest {
    private fun root(): File = Files.createTempDirectory("vico-session-test-").toFile()
    private fun metadata() = SessionRecorder.Metadata(9007199254740993L, 1700000000000, "daca63c", "RX7", "sha256:abc")
    private fun offerEventually(s: SessionRecorder, kind: SessionRecorder.Kind, ns: Long, frame: Long, epoch: Long, values: Array<out Number?>): Boolean {
        val deadline = System.nanoTime() + 1_000_000_000L
        do {
            if (s.offer(kind, ns, frame, epoch, values)) return true
            Thread.sleep(1)
        } while (System.nanoTime() < deadline && s.status().state == SessionRecorder.State.RECORDING)
        return false
    }
    private fun gps() = arrayOf<Number?>(9007199254740993L, 9007199254740994L, 70.0 / 3.6, 0.5, 1, 1, 1, 5.0, 1)
    @Test fun exactNanosecondsAndSnapshotAndPrivacy() {
        val s = SessionRecorder.start(root(), metadata())
        val values = gps()
        assertTrue(offerEventually(s, SessionRecorder.Kind.GPS, 9007199254740995L, 42, 3, values))
        values[0] = 0L
        s.stop(); assertTrue(s.awaitClosed(5000))
        val text = File(s.directory, "records.tsv").readText()
        assertTrue(text.contains("GPS\t9007199254740995\t42\t3\t9007199254740993"))
        assertFalse(text.contains("latitude")); assertFalse(text.contains("longitude"))
        assertEquals(SessionRecorder.State.COMPLETE, s.status().state)
        assertEquals(1L, s.status().written)
        assertFalse(File(s.directory, "records.partial.tsv").exists())
    }
    @Test fun frozenV2SchemaAndConfigurationManifest() {
        assertEquals(2, SessionRecorder.SCHEMA_VERSION)
        assertEquals("config_revision_id,unit_code,mount_axis_code,mount_confirmed,calibration_revision_id,bias_x_mps2,bias_y_mps2,bias_z_mps2,gps_fresh_ms,imu_fresh_ms,gps_uncertainty_threshold_mps,display_unit_code", SessionRecorder.Kind.CONFIG.fields)
        assertEquals(1, SessionRecorder.Kind.CONTROL.fieldNames.indexOf("control_frame_id"))
        assertEquals(4, SessionRecorder.Kind.MODEL.fieldNames.indexOf("valid_until_ns"))
        assertEquals(20, SessionRecorder.Kind.MODEL.fieldNames.indexOf("afterfire_cause"))
        assertEquals(21, SessionRecorder.Kind.MODEL.fieldNames.indexOf("afterfire_source_id"))
        val s = SessionRecorder.start(root(), metadata().copy(buildId="apk:" + "a".repeat(64), androidApi=34, deviceModel="Pixel_9"))
        val config = arrayOf<Number?>(1L, 1, 2, 1, 5L, 0.1, -0.2, 0.3, 2000.0, 100.0, 3.0, 1)
        assertTrue(offerEventually(s, SessionRecorder.Kind.CONFIG, 1, 0, 0, config))
        val invalid = config.copyOf(); invalid[1] = 99
        assertFalse(s.offer(SessionRecorder.Kind.CONFIG, 2, 0, 0, invalid))
        val event = arrayOf<Number?>(4, 1, 9007199254740993L, 9007199254740994L, 42L, 4000.0, 3, 0.0, 0.2, 100L, 200L, 1L)
        assertTrue(offerEventually(s, SessionRecorder.Kind.EVENT, 200, 42, 3, event))
        s.stop(); assertTrue(s.awaitClosed(5000))
        val text = File(s.directory,"records.tsv").readText()
        assertTrue(text.contains("# vico_session_schema=2"))
        assertTrue(text.contains("android_api=34 device_model=Pixel_9"))
        assertEquals(8, SessionRecorder.Kind.GPS.fieldNames.indexOf("has_speed"))
        assertEquals(11, SessionRecorder.Kind.CONFIG.fieldNames.indexOf("display_unit_code"))
        assertEquals(13, SessionRecorder.Kind.IMU.fieldNames.indexOf("config_revision_id"))
        assertEquals(6, SessionRecorder.Kind.UI_ACK.fieldNames.indexOf("display_value"))
        assertTrue(text.contains("# enum.afterfire_cause=0:NONE,1:RELEASE,2:SHIFT"))
        assertTrue(text.contains("# enum.source_mode=0:UNSPECIFIED,1:REAL,2:DEMO,3:PREVIEW,4:QUALIFICATION"))
        assertTrue(text.contains("EVENT\t200\t42\t3\t4\t1\t9007199254740993\t9007199254740994"))
        assertEquals(2L,s.status().written); assertEquals(1L,s.status().rejected)
    }
    @Test fun audioWindowCountIsExactAndAppended() {
        assertEquals(10, SessionRecorder.Kind.AUDIO.fieldNames.indexOf("blocks_in_window"))
        val s = SessionRecorder.start(root(), metadata())
        val audio = arrayOf<Number?>(50L, 44100, 1024, 0, 1000L, 2000L, 5120, 2, 0.5, 1, 5L)
        assertTrue(offerEventually(s, SessionRecorder.Kind.AUDIO, 100, 10, 1, audio))
        val invalid = audio.copyOf(); invalid[10] = 5.0
        assertFalse(s.offer(SessionRecorder.Kind.AUDIO, 101, 10, 1, invalid))
        s.stop(); assertTrue(s.awaitClosed(5000))
        assertEquals(1L, s.status().written); assertEquals(1L, s.status().rejected)
    }
    @Test fun rejectsFloatingPointNanoseconds() {
        val s = SessionRecorder.start(root(), metadata())
        val values = gps(); values[0] = 9007199254740992.0
        assertFalse(s.offer(SessionRecorder.Kind.GPS, 1, 1, 1, values))
        s.stop(); assertTrue(s.awaitClosed(5000))
        assertEquals(1L, s.status().rejected)
    }
    @Test fun invalidRecordsAndStoppedOffersAreCounted() {
        val s = SessionRecorder.start(root(), metadata())
        assertFalse(s.offer(SessionRecorder.Kind.GPS, 1, 1, 1, arrayOf(Double.NaN)))
        assertFalse(s.offer(SessionRecorder.Kind.GPS, -1, 1, 1, gps()))
        s.stop(); assertTrue(s.awaitClosed(5000))
        assertFalse(s.offer(SessionRecorder.Kind.GPS, 1, 1, 1, gps()))
        assertEquals(3L, s.status().rejected)
    }
    @Test fun byteCapStopsWithoutDeletingAndAccountsAcceptedRows() {
        val root = root()
        File(root, "keep.txt").writeText("user log")
        val s = SessionRecorder.start(root, metadata(), SessionRecorder.Limits(8192, 8192, 20, 100000))
        repeat(10000) { s.offer(SessionRecorder.Kind.GPS, it.toLong(), it.toLong(), 0, gps()) }
        s.stop(); assertTrue(s.awaitClosed(5000))
        val status = s.status()
        assertEquals(SessionRecorder.State.CAPACITY, status.state)
        assertTrue(File(s.directory, "records.tsv").length() <= 8192)
        assertEquals(status.accepted, status.written + status.unwritten)
        assertEquals(10000L, status.accepted + status.queueDropped + status.rejected)
        assertEquals("user log", File(root, "keep.txt").readText())
    }
    @Test fun boundedQueueConcurrentProducerAccounting() {
        val s = SessionRecorder.start(root(), metadata(), SessionRecorder.Limits(queueRecords = 1))
        val threads = (1..4).map { Thread { repeat(10000) { s.offer(SessionRecorder.Kind.GPS, it.toLong(), it.toLong(), 0, gps()) } }.apply { start() } }
        threads.forEach { it.join() }; s.stop(); assertTrue(s.awaitClosed(5000))
        val status = s.status()
        assertTrue(status.queueDropped > 0)
        assertEquals(40000L, status.accepted + status.queueDropped + status.rejected)
        assertEquals(status.accepted, status.written)
    }
    @Test fun countAndByteAdmissionDoNotDeleteExistingLogs() {
        val root = root()
        val first = SessionRecorder.start(root, metadata(), SessionRecorder.Limits(sessionBytes=16000, retainedBytes=20000))
        try { SessionRecorder.start(root, metadata(), SessionRecorder.Limits(sessionBytes=8192, retainedBytes=20000)); fail("active reservation must apply actual first-session cap") } catch (_: IllegalArgumentException) { }
        first.stop(); assertTrue(first.awaitClosed(5000))
        try { SessionRecorder.start(root, metadata(), SessionRecorder.Limits(retainedSessions=1)); fail("count") } catch (_: IllegalArgumentException) { }
        assertTrue(File(first.directory, "records.tsv").exists())
    }
    @Test fun failedFinalizeKeepsRecoverablePartial() {
        val s = SessionRecorder.start(root(), metadata())
        val target = File(s.directory, "records.tsv"); assertTrue(target.mkdir())
        File(target, "occupied").writeText("x")
        assertTrue(offerEventually(s, SessionRecorder.Kind.GPS, 1, 1, 1, gps()))
        s.stop(); assertTrue(s.awaitClosed(5000))
        assertEquals(SessionRecorder.State.IO_FAILED, s.status().state)
        assertTrue(File(s.directory, "records.partial.tsv").readText().contains("GPS\t1\t1\t1"))
    }
}
