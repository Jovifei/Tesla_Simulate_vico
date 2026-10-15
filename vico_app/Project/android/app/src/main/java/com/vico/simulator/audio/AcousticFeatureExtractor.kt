package com.vico.simulator.audio

import com.vico.simulator.sound.S13CaptureBinding
import com.vico.simulator.sound.S13PcmCaptureReport

/** Offline capture-bound features. No reference PCM comparison or acoustic qualification is implemented. */
class AcousticFeatureExtractor(
    private val sampleRateHz: Int = PcmArtifactHashValidator.SAMPLE_RATE_HZ,
    private val algorithmVersion: String = N3FeatureWindowAnalyzer.ALGORITHM_VERSION,
    private val maxSamples: Int = N3FeatureWindowAnalyzer.HARD_MAX_SAMPLES,
) {
    init {
        require(sampleRateHz == PcmArtifactHashValidator.SAMPLE_RATE_HZ) { "capture schema is fixed at 48000 Hz" }
        require(algorithmVersion == N3FeatureWindowAnalyzer.ALGORITHM_VERSION) { "unsupported algorithm" }
        require(maxSamples in 2048..N3FeatureWindowAnalyzer.HARD_MAX_SAMPLES) { "invalid extraction bound" }
    }

    /** Identity metadata alone cannot establish reference alignment or a PCM comparison. */
    data class ArtifactIdentity(
        val sha256: String,
        val sampleRateHz: Int,
        val channels: Int,
        val captureDomain: String,
        val independentlyAligned: Boolean = false,
    )

    data class Result(
        val algorithm: String,
        val samples: Int,
        val rms: Double,
        val evaluation: String,
        val referenceState: String,
        val sha256: String,
        val sampleRateHz: Int,
        val channels: Int,
        val format: String,
        val captureDomain: String,
        val captureBinding: S13CaptureBinding?,
        val features: N3FeatureWindowAnalyzer.Result,
        val harmonicOrderState: String = "NOT_EVALUATED/no_time_aligned_rpm_state",
    ) {
        fun toJson(): String = buildString {
            append("{\"schema\":\"vico.n3.pcm_features.v1\"")
            append(",\"algorithm\":" + quote(algorithm))
            append(",\"samples\":$samples,\"sample_rate_hz\":$sampleRateHz,\"channels\":$channels")
            append(",\"format\":" + quote(format) + ",\"domain\":" + quote(captureDomain))
            append(",\"pcm_sha256\":" + quote(sha256))
            append(",\"evaluation\":" + quote(evaluation) + ",\"reference_state\":" + quote(referenceState))
            append(",\"comparison_status\":\"NOT_EVALUATED\",\"comparison_errors\":null")
            append(",\"harmonic_order_state\":" + quote(harmonicOrderState))
            append(",\"capture_binding\":")
            val binding = captureBinding
            if (binding == null) append("null") else {
                append("{\"vehicle_key\":" + quote(binding.vehicleKey))
                append(",\"source_commit\":" + quote(binding.sourceCommit))
                append(",\"trace_sha256\":" + quote(binding.traceSha256))
                append(",\"bank_manifest_sha256\":" + quote(binding.bankManifestSha256))
                append(",\"event_schedule_sha256\":" + quote(binding.eventScheduleSha256) + "}")
            }
            append(",\"features\":{")
            append("\"rms\":$rms,\"zero_crossings\":${features.zeroCrossings}")
            append(",\"low_band_energy\":${features.lowBandEnergy},\"low_band_hz\":[0,500]")
            append(",\"high_band_energy\":${features.highBandEnergy},\"high_band_hz\":[2000,8000]")
            append(",\"spectral_mean_square\":${features.spectralMeanSquare}")
            append(",\"energy_units\":" + quote(features.energyUnits))
            append(",\"normalization\":" + quote(features.normalization))
            append(",\"window\":" + quote(features.window))
            append(",\"lag_one_correlation\":${features.lagOneCorrelation}")
            append(",\"lag_one_definition\":\"UNCENTERED_NORMALIZED_ADJACENT_SAMPLE_CORRELATION\"")
            append(",\"peak_absolute\":${features.peakAbsolute},\"crest_factor\":${features.crestFactor}")
            append(",\"max_adjacent_step\":${features.maxAdjacentStep}")
            append(",\"frame_size\":${features.frameSize},\"hop_size\":${features.hopSize}")
            append(",\"spectrum_frames\":${features.spectrumFrames}")
            append(",\"spectrum_covered_samples\":${features.spectrumCoveredSamples}")
            append(",\"trailing_samples\":${features.trailingSamples}}}")
        }

        private fun quote(value: String): String = buildString {
            append('"')
            for (character in value) when (character) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                else -> if (character.code < 32) append("\\u%04x".format(character.code)) else append(character)
            }
            append('"')
        }
    }

    fun extract(pcm: FloatArray, capture: S13PcmCaptureReport, reference: ArtifactIdentity? = null): Result {
        require(pcm.size <= maxSamples) { "pcm exceeds bounded extraction window" }
        PcmArtifactHashValidator.validate(capture, pcm).getOrThrow()
        val features = N3FeatureWindowAnalyzer(sampleRateHz, maxSamples).analyze(pcm)
        val referenceState = when {
            reference == null -> "NOT_EVALUATED/missing_reference"
            reference.sampleRateHz != sampleRateHz || reference.channels != 1 -> "NOT_EVALUATED/reference_format_mismatch"
            reference.captureDomain != capture.captureDomain -> "NOT_EVALUATED/reference_domain_mismatch"
            else -> "NOT_EVALUATED/reference_pcm_comparison_not_implemented"
        }
        return Result(algorithmVersion, pcm.size, features.rms, "MEASURED_FEATURE_ONLY", referenceState,
            capture.sha256.lowercase(), sampleRateHz, PcmArtifactHashValidator.CHANNELS,
            PcmArtifactHashValidator.FORMAT, capture.captureDomain, capture.binding, features)
    }
}
