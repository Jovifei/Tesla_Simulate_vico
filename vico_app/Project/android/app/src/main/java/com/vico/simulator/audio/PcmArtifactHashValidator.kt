package com.vico.simulator.audio

import com.vico.simulator.sound.S13PcmCaptureReport
import java.security.MessageDigest

/** Validates exported PCM identity; a caller supplied non-empty hash is not sufficient. */
object PcmArtifactHashValidator {
    fun validate(report: S13PcmCaptureReport, pcm: FloatArray): Result<Unit> = runCatching {
        require(report.fullWindow) { "capture window incomplete" }
        require(pcm.size == report.capturedFrames) { "pcm frame mismatch" }
        require(pcm.all { it.isFinite() }) { "non-finite pcm" }
        val digest = MessageDigest.getInstance("SHA-256")
        pcm.forEach { sample ->
            val bits = java.lang.Float.floatToIntBits(sample)
            digest.update(byteArrayOf(
                (bits and 0xff).toByte(),
                ((bits ushr 8) and 0xff).toByte(),
                ((bits ushr 16) and 0xff).toByte(),
                ((bits ushr 24) and 0xff).toByte(),
            ))
        }
        val calculated = digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
        require(calculated.equals(report.sha256, ignoreCase = true)) { "pcm hash mismatch" }
    }
}
