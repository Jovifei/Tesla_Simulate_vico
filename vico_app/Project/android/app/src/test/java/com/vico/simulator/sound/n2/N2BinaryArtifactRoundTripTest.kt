package com.vico.simulator.sound.n2

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class N2BinaryArtifactRoundTripTest {
    @Test fun profileArraysSurviveBinaryRoundTrip() {
        val original = N2Profile.preregistered()
        val loaded = N2ProfileArtifactLoader.export(original).profile
        assertEquals(original.identity, loaded.identity)
        assertEquals(original.sourceScale, loaded.sourceScale, 0.0)
        assertEquals(original.eventScale, loaded.eventScale, 0.0)
        repeat(N2Profile.BASIS_COUNT) { assertArrayEquals(original.basis(it), loaded.basis(it), 0.0) }
        assertArrayEquals(original.coefficients(), loaded.coefficients(), 0.0)
        assertArrayEquals(original.eventResponse(), loaded.eventResponse(), 0.0)
        assertArrayEquals(original.eventNoiseA(), loaded.eventNoiseA(), 0.0)
        assertArrayEquals(original.eventNoiseB(), loaded.eventNoiseB(), 0.0)
        assertEquals(original.sourceSeed, loaded.sourceSeed)
        assertEquals(original.occurrenceSeed, loaded.occurrenceSeed)
        assertEquals(original.responseSeed, loaded.responseSeed)
        assertEquals(original.randomFraction, loaded.randomFraction, 0.0)
        assertEquals(original.eventNoiseFraction, loaded.eventNoiseFraction, 0.0)
    }

    @Test fun tamperedAndTruncatedArtifactsReject() {
        val bytes = N2ProfileArtifactLoader.export(N2Profile.preregistered()).bytes
        assertThrows(IllegalArgumentException::class.java) {
            N2ProfileArtifactLoader.import(bytes.copyOf(bytes.size - 8))
        }
        val bad = bytes.copyOf()
        bad[12] = (bad[12].toInt() xor 0x7f).toByte()
        assertThrows(IllegalArgumentException::class.java) {
            N2ProfileArtifactLoader.import(bad)
        }
        assertThrows(IllegalArgumentException::class.java) {
            N2ProfileArtifactLoader.import(bytes + byteArrayOf(0))
        }
    }
}
