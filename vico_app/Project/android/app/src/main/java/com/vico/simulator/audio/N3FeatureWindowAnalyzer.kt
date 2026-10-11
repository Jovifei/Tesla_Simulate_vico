package com.vico.simulator.audio

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** Offline diagnostics. Rectangular complete frames only; no padding, tuning or gain. */
class N3FeatureWindowAnalyzer(
    private val sampleRateHz: Int = 48000,
    private val maxSamples: Int = HARD_MAX_SAMPLES,
    private val frameSize: Int = 2048,
    private val hopSize: Int = 1024,
) {
    init {
        require(sampleRateHz == 48000 || sampleRateHz == 96000) { "unsupported sample rate" }
        require(frameSize in 256..4096 && frameSize and (frameSize - 1) == 0) { "frame must be radix-2, 256..4096" }
        require(hopSize in frameSize / 2..frameSize) { "hop must be frame/2..frame" }
        require(maxSamples in frameSize..HARD_MAX_SAMPLES) { "invalid extraction bound" }
    }

    data class Result(
        val rms: Double,
        val zeroCrossings: Int,
        val lowBandEnergy: Double,
        val highBandEnergy: Double,
        val lagOneCorrelation: Double?,
        val spectralMeanSquare: Double,
        val peakAbsolute: Double,
        val crestFactor: Double?,
        val maxAdjacentStep: Double,
        val spectrumFrames: Int,
        val spectrumCoveredSamples: Int,
        val trailingSamples: Int,
        val sampleRateHz: Int,
        val frameSize: Int,
        val hopSize: Int,
        val normalization: String = "ONE_SIDED_PARSEVAL_MEAN_SQUARE",
        val energyUnits: String = "PCM_AMPLITUDE_SQUARED",
        val window: String = "RECTANGULAR_COMPLETE_FRAMES",
    )

    fun analyze(pcm: FloatArray): Result {
        require(pcm.size in frameSize..maxSamples) { "pcm must contain a complete frame within hard bound" }
        require(pcm.all { it.isFinite() }) { "non-finite pcm" }
        var sumSquares = 0.0
        var peak = 0.0
        var maxStep = 0.0
        var crossings = 0
        var lagProduct = 0.0
        var lagLeftSquares = 0.0
        var lagRightSquares = 0.0
        for (i in pcm.indices) {
            val x = pcm[i].toDouble()
            sumSquares += x * x
            peak = maxOf(peak, abs(x))
            if (i > 0) {
                val previous = pcm[i - 1].toDouble()
                if ((previous < 0.0) != (x < 0.0)) crossings++
                maxStep = maxOf(maxStep, abs(x - previous))
                lagProduct += x * previous
                lagLeftSquares += previous * previous
                lagRightSquares += x * x
            }
        }
        val rms = sqrt(sumSquares / pcm.size)
        val lagDenominator = sqrt(lagLeftSquares * lagRightSquares)
        val correlation = if (lagDenominator > 0.0) (lagProduct / lagDenominator).coerceIn(-1.0, 1.0) else null
        val real = DoubleArray(frameSize)
        val imaginary = DoubleArray(frameSize)
        var low = 0.0
        var high = 0.0
        var spectralMeanSquare = 0.0
        var frames = 0
        var start = 0
        var covered = 0
        while (start <= pcm.size - frameSize) {
            for (i in 0 until frameSize) real[i] = pcm[start + i].toDouble()
            imaginary.fill(0.0)
            fft(real, imaginary)
            val denominator = frameSize.toDouble() * frameSize
            for (bin in 0..frameSize / 2) {
                // Negative-frequency partners contribute equally except DC and Nyquist.
                val weight = if (bin == 0 || bin == frameSize / 2) 1.0 else 2.0
                val energy = weight * (real[bin] * real[bin] + imaginary[bin] * imaginary[bin]) / denominator
                val hz = bin.toDouble() * sampleRateHz / frameSize
                spectralMeanSquare += energy
                if (hz <= 500.0) low += energy
                if (hz in 2000.0..8000.0) high += energy
            }
            frames++
            covered = start + frameSize
            start += hopSize
        }
        return Result(rms, crossings, low / frames, high / frames, correlation,
            spectralMeanSquare / frames, peak, if (rms > 0.0) peak / rms else null,
            maxStep, frames, covered, pcm.size - covered, sampleRateHz, frameSize, hopSize)
    }

    /** Deterministic in-place radix-2 FFT, O(N log N), two reusable N-sized buffers. */
    private fun fft(real: DoubleArray, imaginary: DoubleArray) {
        var reversed = 0
        for (i in 1 until frameSize) {
            var bit = frameSize shr 1
            while (reversed and bit != 0) {
                reversed = reversed xor bit
                bit = bit shr 1
            }
            reversed = reversed xor bit
            if (i < reversed) {
                val tmp = real[i]
                real[i] = real[reversed]
                real[reversed] = tmp
            }
        }
        var length = 2
        while (length <= frameSize) {
            val angle = -2.0 * Math.PI / length
            val rootReal = cos(angle)
            val rootImaginary = sin(angle)
            for (start in 0 until frameSize step length) {
                var twiddleReal = 1.0
                var twiddleImaginary = 0.0
                for (j in 0 until length / 2) {
                    val left = start + j
                    val right = left + length / 2
                    val productReal = real[right] * twiddleReal - imaginary[right] * twiddleImaginary
                    val productImaginary = real[right] * twiddleImaginary + imaginary[right] * twiddleReal
                    real[right] = real[left] - productReal
                    imaginary[right] = imaginary[left] - productImaginary
                    real[left] += productReal
                    imaginary[left] += productImaginary
                    val nextReal = twiddleReal * rootReal - twiddleImaginary * rootImaginary
                    twiddleImaginary = twiddleReal * rootImaginary + twiddleImaginary * rootReal
                    twiddleReal = nextReal
                }
            }
            length = length shl 1
        }
    }

    companion object {
        const val HARD_MAX_SAMPLES = 1_440_000
        const val ALGORITHM_VERSION = "n3-pcm-radix2-parseval-v1"
    }
}
