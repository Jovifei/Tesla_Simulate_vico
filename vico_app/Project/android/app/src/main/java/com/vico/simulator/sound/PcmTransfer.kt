package com.vico.simulator.sound

import java.io.OutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

data class S13CaptureBinding(
    val vehicleKey: String,
    val sourceCommit: String,
    val traceSha256: String,
    val bankManifestSha256: String,
    val eventScheduleSha256: String,
)

data class S13PcmCaptureReport(
    val requestedFrames: Long,
    val acceptedFrames: Long,
    val capturedFrames: Int,
    val capacityFrames: Int,
    val overflow: Boolean,
    val failed: Boolean,
    val sha256: String,
    val binding: S13CaptureBinding? = null,
    val captureDomain: String = "POST_ENVELOPES_PRE_AUDIOTRACK_ACCEPTED",
) {
    val fullWindow: Boolean
        get() = requestedFrames == S13ReviewContract.TOTAL_FRAMES.toLong() &&
            acceptedFrames == S13ReviewContract.TOTAL_FRAMES.toLong() &&
            capturedFrames == S13ReviewContract.TOTAL_FRAMES &&
            capacityFrames == S13ReviewContract.TOTAL_FRAMES && !overflow && !failed

    fun toJson(): String = """
        {"schema":"vico.s13.pcm_capture.v1","sample_rate_hz":48000,"channels":1,
        "format":"f32le","domain":"$captureDomain",
        "input_binding":"${if (binding == null) "UNBOUND" else "MATCHED_TRACE"}",
        "vehicle_key":${binding?.vehicleKey?.let { "\"$it\"" } ?: "null"},
        "source_commit":${binding?.sourceCommit?.let { "\"$it\"" } ?: "null"},
        "trace_sha256":${binding?.traceSha256?.let { "\"$it\"" } ?: "null"},
        "bank_manifest_sha256":${binding?.bankManifestSha256?.let { "\"$it\"" } ?: "null"},
        "event_schedule_sha256":${binding?.eventScheduleSha256?.let { "\"$it\"" } ?: "null"},
        "comparison_status":"NOT_EVALUATED",
        "target_frames":1440000,"requested_frames":$requestedFrames,
        "accepted_frames":$acceptedFrames,"captured_frames":$capturedFrames,
        "capacity_frames":$capacityFrames,"overflow":$overflow,"failed":$failed,
        "full_window":$fullWindow,"sha256":"$sha256"}
    """.trimIndent()
}

/** Single writer; export only after finish so the audio thread never writes files. */
internal class BoundedPcmCapture(
    val capacityFrames: Int = S13ReviewContract.TOTAL_FRAMES,
    private val binding: S13CaptureBinding? = null,
    private val captureDomain: String = "POST_ENVELOPES_PRE_AUDIOTRACK_ACCEPTED",
) {
    private val samples = FloatArray(capacityFrames.also {
        require(it in 1..S13ReviewContract.TOTAL_FRAMES)
    })
    private var requested = 0L
    private var accepted = 0L
    private var captured = 0
    private var overflow = false
    private var failed = false

    @Volatile
    var isFinished = false
        private set

    fun beginBlock(count: Int) {
        check(!isFinished)
        require(count >= 0)
        requested += count
    }

    fun accept(data: FloatArray, offset: Int, count: Int) {
        check(!isFinished)
        require(offset >= 0 && count >= 0 && offset.toLong() + count <= data.size)
        accepted += count
        val copied = minOf(count, capacityFrames - captured)
        if (copied > 0) System.arraycopy(data, offset, samples, captured, copied)
        captured += copied
        if (copied < count) overflow = true
    }

    fun markFailed() {
        failed = true
    }

    fun finish() {
        isFinished = true
    }

    /** Does not close the caller-owned stream. Call this off the audio thread. */
    fun exportF32le(output: OutputStream): S13PcmCaptureReport {
        check(isFinished) { "Capture is still being written" }
        val digest = MessageDigest.getInstance("SHA-256")
        val page = ByteBuffer.allocate(4096).order(ByteOrder.LITTLE_ENDIAN)
        var index = 0
        while (index < captured) {
            page.clear()
            val count = minOf(page.capacity() / 4, captured - index)
            repeat(count) { page.putFloat(samples[index++]) }
            output.write(page.array(), 0, page.position())
            digest.update(page.array(), 0, page.position())
        }
        output.flush()
        val hash = digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
        return S13PcmCaptureReport(
            requestedFrames = requested,
            acceptedFrames = accepted,
            capturedFrames = captured,
            capacityFrames = capacityFrames,
            overflow = overflow,
            failed = failed,
            sha256 = hash,
            binding = binding,
            captureDomain = captureDomain,
        )
    }
}

/** Completes each PCM block or fails; zero progress never spins indefinitely. */
internal fun writeAllPcm(
    pcm: FloatArray,
    capture: BoundedPcmCapture? = null,
    writer: (FloatArray, Int, Int) -> Int,
) {
    try {
        capture?.beginBlock(pcm.size)
        require(pcm.all { it.isFinite() }) { "Non-finite PCM block" }
        var offset = 0
        while (offset < pcm.size) {
            val remaining = pcm.size - offset
            val count = writer(pcm, offset, remaining)
            check(count in 1..remaining) {
                "PCM write failed: accepted=$count offset=$offset remaining=$remaining"
            }
            capture?.accept(pcm, offset, count)
            offset += count
        }
    } catch (error: Exception) {
        capture?.markFailed()
        throw error
    }
}
