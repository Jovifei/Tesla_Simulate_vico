package com.vico.simulator.sound

import java.nio.ByteBuffer
import java.nio.ByteOrder

data class FloatWav(val sampleRateHz: Int, val samples: FloatArray)

object FloatWavDecoder {
    fun decode(bytes: ByteArray): FloatWav {
        require(bytes.size >= 44 && ascii(bytes, 0) == "RIFF" && ascii(bytes, 8) == "WAVE") {
            "Invalid RIFF/WAVE asset"
        }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        var position = 12
        var format = 0
        var channels = 0
        var sampleRate = 0
        var bits = 0
        var dataOffset = -1
        var dataSize = 0
        while (position + 8 <= bytes.size) {
            val id = ascii(bytes, position)
            val size = buffer.getInt(position + 4)
            val content = position + 8
            if (size < 0 || content + size > bytes.size) break
            if (id == "fmt ") {
                format = buffer.getShort(content).toInt() and 0xffff
                channels = buffer.getShort(content + 2).toInt() and 0xffff
                sampleRate = buffer.getInt(content + 4)
                bits = buffer.getShort(content + 14).toInt() and 0xffff
            } else if (id == "data") {
                dataOffset = content
                dataSize = size
                break
            }
            position = content + size + (size and 1)
        }
        require(format == 3 && channels == 1 && bits == 32 && (sampleRate == 48000 || sampleRate == 96000) && dataOffset >= 0) {
            "Expected mono 48/96 kHz IEEE-float WAV"
        }
        val count = dataSize / 4
        val samples = FloatArray(count) { index -> buffer.getFloat(dataOffset + index * 4) }
        return FloatWav(sampleRate, samples)
    }

    private fun ascii(bytes: ByteArray, offset: Int): String =
        String(bytes, offset, 4, Charsets.US_ASCII)
}
