package com.vico.simulator.sound

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Original reference PCM, without another gain, envelope or sensor mapping. */
class S14ReferenceSession(bytes: ByteArray, val label: String) {
    val expectedSha = when (label) {
        "R" -> "2d66e9adcc763619c1152dc124ceb73b7c9f128a0693925e6ab4197f507cc7a2"
        "M" -> "127f2c08a9977e43510633bbbad44ee989f7d112b79d5876bff99b99a7ef0b4f"
        else -> error("Unknown S14 material")
    }
    private val samples: FloatArray
    var framesRendered = 0
        private set
    val isComplete get() = framesRendered == S13ReviewContract.TOTAL_FRAMES

    init {
        require(bytes.size == S13ReviewContract.TOTAL_FRAMES * 4)
        S13ReviewContract.requireSha256(bytes, expectedSha)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        samples = FloatArray(S13ReviewContract.TOTAL_FRAMES) { buffer.float }
        require(samples.all { it.isFinite() && kotlin.math.abs(it) <= 1f })
    }

    fun renderNext(): FloatArray? {
        if (isComplete) return null
        val end = minOf(framesRendered + S13ReviewContract.BLOCK_FRAMES, samples.size)
        return samples.copyOfRange(framesRendered, end).also { framesRendered = end }
    }
}
