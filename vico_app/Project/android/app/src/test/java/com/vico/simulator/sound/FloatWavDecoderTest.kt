package com.vico.simulator.sound

import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class FloatWavDecoderTest {

    @Test
    fun decodes_matlab_96khz_ieee_float_wav_without_quantization() {
        val expected = floatArrayOf(-0.5f, 0.25f, 0.875f)
        val bytes = ByteBuffer.allocate(44 + expected.size * 4)
            .order(ByteOrder.LITTLE_ENDIAN)
            .apply {
                put("RIFF".toByteArray()); putInt(36 + expected.size * 4)
                put("WAVE".toByteArray()); put("fmt ".toByteArray()); putInt(16)
                putShort(3); putShort(1); putInt(96000); putInt(96000 * 4)
                putShort(4); putShort(32); put("data".toByteArray())
                putInt(expected.size * 4); expected.forEach { putFloat(it) }
            }.array()

        val decoded = FloatWavDecoder.decode(bytes)

        assertEquals(96000, decoded.sampleRateHz)
        assertArrayEquals(expected, decoded.samples, 0f)
    }
}
