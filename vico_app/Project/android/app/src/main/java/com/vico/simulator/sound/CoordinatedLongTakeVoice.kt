package com.vico.simulator.sound

import java.security.MessageDigest
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.pow

/**
 * HC-C1 opt-in experimental coordinated voice. NEVER reads source media, uses
 * only the caller's bounded and F32LE-hash-verified mono take. Not OEM evidence.
 * No allocations or hashing within the audio-thread sample loop.
 */
class CoordinatedLongTakeVoice private constructor(
    private val samples: FloatArray,
    private val regions: List<Region>,
    val pcmSha256: String,
    val sourceClass: String,
) {
    data class Evidence(
        val sourceClass: String,
        val licenseGate: String,
        val captureState: String,
        val phaseState: String,
        val holdoutState: String,
        val approvalId: String = "",
    )
    data class Region(
        val id: String, val startFrame: Int, val endFrame: Int,
        val cycles720: Int, val referenceRpm: Double, val referenceLoad: Double,
    ) {
        val span: Int get() = endFrame - startFrame
    }
    data class Take(
        val vehicleKey: String, val sampleRate: Int, val takeId: String,
        val samples: FloatArray, val pcmSha256: String,
        val evidence: Evidence, val regions: List<Region>,
    )
    data class Snapshot(
        val sourceClass: String, val sourceSha256: String,
        val activeRegion: String?, val renderedFrames: Long,
        val phaseCycles720: Double, val switches: Int, val nonfinite: Int,
        val peak: Double, val cancelled: Boolean,
        val qualification: String = "ENGINEERING_ONLY_NOT_OEM",
    )
    private var cycles = 0.0
    private var active = -1
    private var target = -1
    private var transition = 0
    private var dwell = 12000
    private var rpm = 1000.0
    private var load = 0.0
    private var cancelled = false
    private var frames = 0L
    private var switches = 0
    private var peak = 0.0
    private var nonfinite = 0
    val sampleRate = 48000

    fun snapshot() = Snapshot(sourceClass, pcmSha256, regions.getOrNull(active)?.id,
        frames, cycles, switches, nonfinite, peak, cancelled)

    fun cancel() {
        cancelled = true
        target = -1
    }

    fun setControl(requestedRpm: Double, requestedLoad: Double) {
        require(requestedRpm.isFinite() && requestedRpm >= 0 &&
            requestedLoad.isFinite() && requestedLoad in 0.0..1.0) {
            "Invalid coordinated voice state"
        }
        if (cancelled) return
        rpm = requestedRpm.coerceIn(500.0, 10000.0)
        load = requestedLoad
        fun score(r: Region) =
            (ln(rpm / r.referenceRpm) / .35).pow(2) +
            ((load - r.referenceLoad) / .30).pow(2)
        val best = regions.indices.minByOrNull { score(regions[it]) } ?: 0
        if (active == -1) { active = best; return }
        if (target != -1 || dwell < 12000) return
        if (best != active && score(regions[best]) + .15 < score(regions[active])) {
            target = best
            transition = 0
            switches++
        }
    }

    private fun read(index: Int): Float {
        val r = regions[index]
        val phase = ((cycles % r.cycles720) + r.cycles720) % r.cycles720
        val position = phase / r.cycles720 * r.span
        val first = floor(position).toInt().coerceIn(0, r.span - 1)
        val second = if (first + 1 == r.span) 0 else first + 1
        val alpha = (position - first).toFloat()
        val a = samples[r.startFrame + first]
        val b = samples[r.startFrame + second]
        return a + (b - a) * alpha
    }

    fun next(): Float {
        if (cancelled) return 0f
        check(active >= 0) { "Coordinated voice has no live RPM/load control" }
        var sample = read(active)
        if (target >= 0) {
            val t = transition.toDouble() / 5760.0
            val mix = (t * t * (3 - 2 * t)).toFloat()
            sample = sample * (1f - mix) + read(target) * mix
            if (++transition >= 5760) {
                active = target
                target = -1
                transition = 0
                dwell = 0
            }
        }
        cycles += rpm / 120.0 / sampleRate
        frames++
        dwell++
        if (!sample.isFinite()) {
            nonfinite++
            throw IllegalStateException("Nonfinite coordinated recorded voice")
        }
        peak = max(peak, abs(sample.toDouble()))
        return sample
    }

    companion object {
        private val hashPattern = Regex("[0-9a-f]{64}")
        private val regionPattern = Regex("[a-z0-9_-]{3,32}")
        private val takePattern = Regex("[A-Za-z0-9_.-]{8,80}")
        private val approvalPattern = Regex("[A-Za-z0-9_.-]{12,96}")

        /**
         * IMPORTANT: preparation must occur off the AudioTrack writer.
         * Verify the complete F32LE identity, length, provenance and state.
         * This does NOT legally determine distribution rights.
         */
        fun prepare(take: Take): CoordinatedLongTakeVoice {
            require(take.vehicleKey == "hellcat_v6" && take.sampleRate == 48000 &&
                take.takeId.matches(takePattern) && take.pcmSha256.matches(hashPattern) &&
                take.samples.size in 96000..(48000 * 60))
            val e = take.evidence
            val synthetic = e.sourceClass == "SYNTHETIC_TEST_ONLY" &&
                e.licenseGate == "NOT_DISTRIBUTABLE_TEST" &&
                e.captureState == "SYNTHETIC_KNOWN_RPM_LOAD" &&
                e.phaseState == "SYNTHETIC_KNOWN_720"
            val product = e.sourceClass == "LICENSED_RECORDED_TAKE" &&
                e.licenseGate == "PRODUCT_DISTRIBUTION_CLEARED" &&
                e.captureState == "SYNCHRONIZED_MEASURED_RPM_LOAD" &&
                e.phaseState == "VERIFIED_720_PHASE" &&
                e.holdoutState == "INDEPENDENT_LOCKED" &&
                e.approvalId.matches(approvalPattern)
            require(synthetic || product) { "Unqualified recorded voice" }
            require(take.regions.size in 2..8) { "Missing multi-state source regions" }
            var lastEnd = 0
            val ids = mutableSetOf<String>()
            for (r in take.regions) {
                require(r.id.matches(regionPattern) && ids.add(r.id) &&
                    r.startFrame >= lastEnd && r.endFrame <= take.samples.size &&
                    r.span in 48000..48000*12 && r.cycles720 in 4..300 &&
                    r.referenceRpm.isFinite() && r.referenceRpm in 500.0..10000.0 &&
                    r.referenceLoad.isFinite() && r.referenceLoad in 0.0..1.0) {
                    "Invalid or overlapping coordinated take segment"
                }
                val expected = r.cycles720 * 120.0 * 48000 / r.span
                require(abs(expected - r.referenceRpm) <= r.referenceRpm * .015) {
                    "RPM/cycle phase metadata inconsistent"
                }
                require(abs(take.samples[r.startFrame] - take.samples[r.endFrame - 1]) <= .12f) {
                    "Source window end is not phase aligned"
                }
                lastEnd = r.endFrame
            }
            for (v in take.samples) require(v.isFinite() && abs(v) <= .55f) {
                "Nonfinite/excessive source sample"
            }
            val snapshot = take.samples.copyOf() // prevents mutation after SHA check
            require(shaF32Le(snapshot) == take.pcmSha256) { "F32LE source SHA mismatch" }
            return CoordinatedLongTakeVoice(snapshot, take.regions.toList(), take.pcmSha256, e.sourceClass)
        }

        private fun shaF32Le(samples: FloatArray): String {
            val sha = MessageDigest.getInstance("SHA-256")
            val bytes = ByteArray(4096 * 4)
            var n = 0
            for (v in samples) {
                val bits = v.toRawBits()
                for (i in 0..3) bytes[n++] = (bits ushr (i * 8)).toByte()
                if (n == bytes.size) {
                    sha.update(bytes)
                    n = 0
                }
            }
            if (n > 0) sha.update(bytes, 0, n)
            return sha.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
