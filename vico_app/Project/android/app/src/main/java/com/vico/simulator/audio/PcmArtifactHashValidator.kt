package com.vico.simulator.audio

import com.vico.simulator.sound.S13PcmCaptureReport
import java.security.MessageDigest

/** Validates the fixed receipt schema: 48 kHz mono f32le, complete accepted capture. */
object PcmArtifactHashValidator {
    const val SAMPLE_RATE_HZ = 48000
    const val CHANNELS = 1
    const val FORMAT = "f32le"
    const val CAPTURE_DOMAIN = "POST_ENVELOPES_PRE_AUDIOTRACK_ACCEPTED"

    fun validate(report: S13PcmCaptureReport, pcm: FloatArray): Result<Unit> = runCatching {
        require(report.fullWindow) { "capture window incomplete" }
        require(pcm.size == report.capturedFrames) { "pcm frame mismatch" }
        require(report.captureDomain in setOf(CAPTURE_DOMAIN,
            "POST_ENVELOPES_PRE_AUDIOTRACK_SUBMISSION", "S14_REFERENCE_PRE_AUDIOTRACK_SUBMISSION")) {
            "unsupported capture domain"
        }
        require(report.sha256.matches(Regex("[0-9a-fA-F]{64}"))) { "invalid pcm SHA-256" }
        require(sha256F32le(pcm).equals(report.sha256, ignoreCase = true)) { "pcm hash mismatch" }
    }

    /** Hash the exact finite float bit patterns serialized little endian, including signed zero. */
    fun sha256F32le(pcm: FloatArray): String {
        require(pcm.isNotEmpty() && pcm.size <= N3FeatureWindowAnalyzer.HARD_MAX_SAMPLES) { "pcm outside hard bound" }
        val digest = MessageDigest.getInstance("SHA-256")
        val bytes = ByteArray(4096)
        var position = 0
        for (sample in pcm) {
            require(sample.isFinite()) { "non-finite pcm" }
            val bits = java.lang.Float.floatToRawIntBits(sample)
            for (shift in 0..24 step 8) bytes[position++] = (bits ushr shift).toByte()
            if (position == bytes.size) {
                digest.update(bytes)
                position = 0
            }
        }
        if (position > 0) digest.update(bytes, 0, position)
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }
}
