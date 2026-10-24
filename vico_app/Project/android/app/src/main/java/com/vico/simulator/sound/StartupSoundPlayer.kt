package com.vico.simulator.sound

import java.security.MessageDigest
import kotlin.math.abs

/** One validated public R2 one-shot, not a calibrated engine or real-driving sound source. */
class StartupSoundPlayer private constructor(private val samples: FloatArray?, private val unavailableReason: String?) {
    data class Snapshot(
        val available: Boolean,
        val stage: String,
        val renderedFrames: Long,
        val peakAbsolute: Double,
        val reason: String?,
        val domain: String = "STARTUP_IDLE_CROSSFADE_PRE_APP_ENVELOPES",
        val assetSha256: String? = null,
        val qualification: String = "PUBLIC_R2_STARTUP_NOT_OEM_CALIBRATION",
    )

    private var stage = if (samples == null) "UNAVAILABLE" else "READY"
    private var armed = false
    private var playing = false
    private var position = 0
    private var epoch = Long.MIN_VALUE
    private var frames = 0L
    private var peak = 0.0

    /** Only the explicit playback preparation owner can arm another start, including the same car. */
    fun resetSession(allowDemoStartup: Boolean = false) {
        armed = samples != null && allowDemoStartup
        playing = false
        position = 0
        epoch = Long.MIN_VALUE
        frames = 0
        peak = 0.0
        stage = if (samples == null) "UNAVAILABLE" else if (armed) "ARMED" else "DISARMED"
    }

    fun cancel() {
        if (armed || playing) stage = "CANCELLED"
        armed = false
        playing = false
    }

    /** The input gate clears transients on the first valid epoch too; preserve a fresh pending arm. */
    fun cancelActive() { if (playing) cancel() }

    /** Mix into the already-rendered continuous bank so its phase/state never pauses or resets.
     * Gate false cancels, it never pauses. No allocation or wall-clock scheduling in this loop.
     */
    fun mixInto(output: FloatArray, state: SoundState, allowStartup: Boolean, vehicleKey: String?) {
        if (output.isEmpty() || samples == null || (!armed && !playing)) return
        val input = state.inputControl
        val speed = state.modelSpeedKmh
        val eligible = allowStartup && vehicleKey == "hellcat_v6" && !state.muted &&
            input?.source == DriveInputSource.DEMO && input.usable && input.epoch >= 0 &&
            state.timeS.isFinite() && state.timeS >= 0 && speed != null && speed.isFinite() && speed in 0.0..1.0
        if (!eligible || (playing && input!!.epoch != epoch)) { cancel(); return }
        if (armed) {
            armed = false
            playing = true
            epoch = input!!.epoch
            stage = "PLAYING"
        }
        for (i in output.indices) {
            if (!playing) break
            val fadeIn = minOf(1.0, position.toDouble() / (FADE_IN_FRAMES - 1))
            val idleShare = if (position < FRAMES - HANDOFF_FRAMES) 0.0 else
                (position - (FRAMES - HANDOFF_FRAMES)).toDouble() / (HANDOFF_FRAMES - 1)
            val value = (samples[position] * fadeIn * (1.0 - idleShare) + output[i] * idleShare).toFloat()
            output[i] = value
            peak = maxOf(peak, abs(value.toDouble()))
            frames++
            if (++position == FRAMES) { playing = false; stage = "ENDED" }
        }
    }

    fun snapshot() = Snapshot(samples != null, stage, frames, peak, unavailableReason,
        assetSha256 = if (samples == null) null else WAV_SHA256)

    companion object {
        const val FRAMES = 314306
        const val WAV_SHA256 = "1b119ab18364e33b64f91459942433817065034366de9b32f4a70283479edb77"
        const val MANIFEST_SHA256 = "1d12720d0cc864d8faa5164dc6231bf224fc0774a3822eb1a34713a58b438426"
        const val ATTRIBUTION_SHA256 = "ac5c2fd4119a5c9dab17ccc5776597d7634c279264dedbd99a9dfffeb73dc70b"
        private const val FADE_IN_FRAMES = 240
        private const val HANDOFF_FRAMES = 7200

        fun unavailable(reason: String) = StartupSoundPlayer(null, reason)

        /** Exact versioned metadata binds public provenance/CC BY-SA4.0, fixed .75 gain and R2 limits.
         * Decode only off the writer thread. Caller-owned bytes are never retained as mutable PCM.
         */
        fun fromValidatedAsset(wav: ByteArray, manifest: ByteArray, attribution: ByteArray, sampleRateHz: Int): StartupSoundPlayer {
            require(sampleRateHz == 48000) { "startup requires 48 kHz bank" }
            require(wav.size == 1257304 && sha(wav) == WAV_SHA256) { "startup WAV identity mismatch" }
            require(manifest.size in 1..8192 && sha(manifest) == MANIFEST_SHA256) { "startup metadata/provenance mismatch" }
            require(attribution.size in 1..8192 && sha(attribution) == ATTRIBUTION_SHA256) { "startup attribution mismatch" }
            val decoded = FloatWavDecoder.decode(wav)
            require(decoded.sampleRateHz == 48000 && decoded.samples.size == FRAMES &&
                decoded.samples.all { it.isFinite() && abs(it) <= 1f }) { "startup PCM specification mismatch" }
            return StartupSoundPlayer(decoded.samples, null)
        }

        private fun sha(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it.toInt() and 255) }
    }
}
