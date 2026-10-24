package com.vico.simulator.audio

import kotlin.math.log10

/** Bounded offline PCM comparison. Never call from the playback thread; no tuning or OEM qualification. */
class AcousticReferenceComparator(
    private val maxSamples: Int = N3FeatureWindowAnalyzer.HARD_MAX_SAMPLES,
) {
    init { require(maxSamples in 2048..N3FeatureWindowAnalyzer.HARD_MAX_SAMPLES) }

    data class PcmIdentity(
        val sha256: String,
        val sampleRateHz: Int,
        val channels: Int,
        val format: String,
        val captureDomain: String,
        val vehicleKey: String,
    )

    /** The caller supplies evidence of prior alignment. This class does not align or verify that evidence. */
    data class Alignment(val independentlyAligned: Boolean, val evidenceId: String)

    /** Signed capture minus reference, using the same analyzer and no loudness normalization. */
    data class Differences(
        val rms: Double,
        val rmsDb: Double,
        val lowBandEnergyRatio: Double,
        val highBandEnergyRatio: Double,
        val crestFactor: Double,
        val spectralMeanSquare: Double,
    )

    data class Comparison(
        val evaluation: String,
        val reason: String?,
        val differences: Differences?,
        val capture: PcmIdentity,
        val reference: PcmIdentity?,
        val samples: Int,
        val alignmentEvidenceId: String?,
        val alignmentState: String = "CALLER_DECLARED_NOT_AUTOMATICALLY_VERIFIED",
    ) {
        fun toJson(): String = buildString {
            append("{\"schema\":\"vico.n3.relative_pcm_comparison.v1\"")
            append(",\"algorithm\":${quote(N3FeatureWindowAnalyzer.ALGORITHM_VERSION)}")
            append(",\"evaluation\":${quote(evaluation)},\"reason\":${quote(reason)}")
            append(",\"samples\":$samples,\"capture_sha256\":${quote(capture.sha256)}")
            append(",\"reference_sha256\":${quote(reference?.sha256)},\"vehicle_key\":${quote(capture.vehicleKey)}")
            append(",\"sample_rate_hz\":${capture.sampleRateHz},\"channels\":${capture.channels}")
            append(",\"format\":${quote(capture.format)},\"domain\":${quote(capture.captureDomain)}")
            append(",\"alignment_state\":${quote(alignmentState)},\"alignment_evidence_id\":${quote(alignmentEvidenceId)}")
            append(",\"qualification\":\"RELATIVE_FEATURES_ONLY_NOT_OEM_SIMILARITY\"")
            append(",\"harmonic_order_state\":\"NOT_EVALUATED/no_time_aligned_rpm_state\"")
            append(",\"difference_direction\":\"CAPTURE_MINUS_REFERENCE\"")
            append(",\"low_band_hz\":[0,500],\"high_band_hz\":[2000,8000]")
            append(",\"band_ratio_denominator\":\"FULL_BAND_SPECTRAL_MEAN_SQUARE\",\"comparison_errors\":")
            val d = differences
            if (d == null) append("null") else {
                append("{\"rms\":${d.rms},\"rms_db\":${d.rmsDb}")
                append(",\"low_band_energy_ratio\":${d.lowBandEnergyRatio},\"high_band_energy_ratio\":${d.highBandEnergyRatio}")
                append(",\"crest_factor\":${d.crestFactor},\"spectral_mean_square\":${d.spectralMeanSquare}}")
            }
            append('}')
        }
    }

    fun compare(
        capturePcm: FloatArray,
        capture: PcmIdentity,
        referencePcm: FloatArray?,
        reference: PcmIdentity?,
        alignment: Alignment?,
    ): Comparison {
        validatePcm(capturePcm, capture)
        fun unavailable(reason: String) = Comparison("NOT_EVALUATED", reason, null, capture, reference,
            capturePcm.size, alignment?.evidenceId)
        if (referencePcm == null || reference == null) return unavailable("missing_reference_pcm_or_identity")
        validatePcm(referencePcm, reference)
        if (capture.sampleRateHz != 48000 || reference.sampleRateHz != 48000) return unavailable("sample_rate_mismatch")
        if (capture.channels != 1 || reference.channels != 1 ||
            capture.format != "f32le" || reference.format != "f32le") return unavailable("channel_or_format_mismatch")
        if (capture.captureDomain !in domains || capture.captureDomain != reference.captureDomain) return unavailable("domain_mismatch")
        if (capture.vehicleKey.isBlank() || reference.vehicleKey.isBlank()) return unavailable("missing_vehicle_identity")
        if (capture.vehicleKey != reference.vehicleKey) return unavailable("vehicle_mismatch")
        if (capturePcm.size != referencePcm.size) return unavailable("frame_count_mismatch")
        if (alignment?.independentlyAligned != true || alignment.evidenceId.isBlank()) return unavailable("alignment_not_established")
        val analyzer = N3FeatureWindowAnalyzer(maxSamples = maxSamples)
        val left = analyzer.analyze(capturePcm)
        val right = analyzer.analyze(referencePcm)
        if (left.rms <= 1e-10 || right.rms <= 1e-10 ||
            left.spectralMeanSquare <= 1e-20 || right.spectralMeanSquare <= 1e-20) {
            return unavailable("silent_capture_or_reference")
        }
        val differences = Differences(left.rms - right.rms, 20 * log10(left.rms / right.rms),
            left.lowBandEnergy / left.spectralMeanSquare - right.lowBandEnergy / right.spectralMeanSquare,
            left.highBandEnergy / left.spectralMeanSquare - right.highBandEnergy / right.spectralMeanSquare,
            requireNotNull(left.crestFactor) - requireNotNull(right.crestFactor),
            left.spectralMeanSquare - right.spectralMeanSquare)
        return Comparison("MEASURED_RELATIVE_COMPARISON", null, differences, capture, reference,
            capturePcm.size, alignment.evidenceId)
    }

    private fun validatePcm(pcm: FloatArray, identity: PcmIdentity) {
        require(pcm.size in 2048..maxSamples) { "pcm outside complete-frame comparison bound" }
        require(identity.sha256.matches(Regex("[0-9a-fA-F]{64}"))) { "invalid PCM SHA-256" }
        require(PcmArtifactHashValidator.sha256F32le(pcm).equals(identity.sha256, ignoreCase = true)) { "PCM hash mismatch" }
    }

    private companion object {
        val domains = setOf(PcmArtifactHashValidator.CAPTURE_DOMAIN,
            "POST_ENVELOPES_PRE_AUDIOTRACK_SUBMISSION", "S14_REFERENCE_PRE_AUDIOTRACK_SUBMISSION")

        fun quote(value: String?): String = if (value == null) "null" else buildString {
            append('"')
            for (c in value) when (c) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                else -> if (c.code < 32) append("\\u%04x".format(c.code)) else append(c)
            }
            append('"')
        }
    }
}
