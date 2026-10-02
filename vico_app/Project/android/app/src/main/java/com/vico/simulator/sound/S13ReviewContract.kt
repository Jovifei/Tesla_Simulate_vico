package com.vico.simulator.sound

import java.security.MessageDigest
import kotlin.math.abs

object S13ReviewContract {
    const val SAMPLE_RATE = 48_000
    const val BLOCK_FRAMES = 960
    const val TOTAL_FRAMES = 1_440_000
    const val TRACE_POINTS = 1501
    const val REVIEW_STOP_FADE_BLOCKS = 20

    fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }

    fun requireSha256(bytes: ByteArray, expected: String) {
        require(expected.matches(Regex("[0-9a-fA-F]{64}"))) { "Invalid SHA-256" }
        require(sha256(bytes).equals(expected, ignoreCase = true)) { "SHA-256 mismatch" }
    }
}

data class S13TracePoint(
    val timeS: Double,
    val rpm: Double,
    val load: Double,
    val throttle: Double,
    val accelerationMps2: Double,
)

/** Typed frame math only; this is not yet an adapter for the packaged JSON trace. */
class S13TraceCursor(points: List<S13TracePoint>) {
    private val points = points.toList()

    init {
        require(this.points.size == S13ReviewContract.TRACE_POINTS)
        this.points.forEachIndexed { index, point ->
            require(point.timeS.isFinite() && point.rpm.isFinite() && point.load.isFinite() &&
                point.throttle.isFinite() && point.accelerationMps2.isFinite())
            require(abs(point.timeS - index / 50.0) <= 1e-9) { "Non-canonical trace time" }
            require(point.rpm >= 0.0 && point.load in 0.0..1.0 && point.throttle in 0.0..1.0)
        }
    }

    /** Linear interpolation; the 30-second endpoint is not rendered. */
    fun at(frame: Int): S13TracePoint {
        require(frame in 0 until S13ReviewContract.TOTAL_FRAMES)
        val index = frame / S13ReviewContract.BLOCK_FRAMES
        val weight = (frame % S13ReviewContract.BLOCK_FRAMES).toDouble() /
            S13ReviewContract.BLOCK_FRAMES
        val first = points[index]
        val second = points[index + 1]
        fun mix(a: Double, b: Double) = a + (b - a) * weight
        return S13TracePoint(
            frame.toDouble() / S13ReviewContract.SAMPLE_RATE,
            mix(first.rpm, second.rpm),
            mix(first.load, second.load),
            mix(first.throttle, second.throttle),
            mix(first.accelerationMps2, second.accelerationMps2),
        )
    }

    /** Includes the final control point only as the interpolation endpoint at frame 30 s. */
    fun atBoundary(frame: Int): S13TracePoint {
        require(frame in 0..S13ReviewContract.TOTAL_FRAMES)
        return if (frame == S13ReviewContract.TOTAL_FRAMES) points.last() else at(frame)
    }
}

data class S13EventBinding(
    val id: String,
    val kind: String,
    val assetPath: String,
    val assetSha256: String,
    val traceSha256: String,
    val sourceDomain: String,
    val sourceTimeS: Double?,
    val sourceFrame: Int?,
    val cropStartFrame: Int?,
    val triggerOffsetFrames: Int?,
    val sampleCount: Int,
) {
    fun validate(
        traceBytes: ByteArray,
        assetBytes: ByteArray,
        decodedFrames: Int,
    ): S13EventPlacement {
        require(id.isNotBlank() && kind in setOf("shift", "afterfire"))
        require(sourceDomain in setOf("TRACE_EVENT", "POST_PTR_STEM_ONSET"))
        require(assetPath.isNotBlank() && !assetPath.startsWith("/") &&
            '\\' !in assetPath && ':' !in assetPath &&
            assetPath.split('/').none { it.isEmpty() || it == "." || it == ".." })
        S13ReviewContract.requireSha256(traceBytes, traceSha256)
        S13ReviewContract.requireSha256(assetBytes, assetSha256)
        val crop = requireNotNull(cropStartFrame) { "BLOCKED_MISSING_EVENT_CROP_START:$id" }
        val source = requireNotNull(sourceFrame) { "BLOCKED_MISSING_EVENT_SOURCE_FRAME:$id" }
        val time = requireNotNull(sourceTimeS) { "BLOCKED_MISSING_EVENT_SOURCE_TIME:$id" }
        val offset = requireNotNull(triggerOffsetFrames) { "BLOCKED_MISSING_EVENT_OFFSET:$id" }
        require(source in 0 until S13ReviewContract.TOTAL_FRAMES)
        require(crop in 0 until S13ReviewContract.TOTAL_FRAMES)
        require(time.isFinite() && time >= 0.0 && time < 30.0)
        require(abs(time * S13ReviewContract.SAMPLE_RATE - source) <= 0.500001)
        require(sampleCount > 0 && sampleCount == decodedFrames)
        val cropEndExclusive = crop.toLong() + decodedFrames.toLong()
        require(cropEndExclusive <= S13ReviewContract.TOTAL_FRAMES.toLong())
        require(source.toLong() >= crop.toLong() && source.toLong() < cropEndExclusive) {
            "Event source frame is outside the decoded clip"
        }
        require(offset >= 0 && offset < decodedFrames) { "Event offset is outside the decoded clip" }
        require(source.toLong() - crop.toLong() == offset.toLong()) { "Event offset mismatch" }
        return S13EventPlacement(this, crop)
    }
}

data class S13EventPlacement internal constructor(
    val binding: S13EventBinding,
    val startFrame: Int,
) {
    fun startsIn(firstFrame: Int, frameCount: Int): Boolean {
        require(firstFrame >= 0 && frameCount >= 0 &&
            firstFrame.toLong() + frameCount <= S13ReviewContract.TOTAL_FRAMES)
        return startFrame >= firstFrame && startFrame < firstFrame.toLong() + frameCount
    }
}
