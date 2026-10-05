package com.vico.simulator.sound.n2

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class N2ArtifactAndStateContractTest {
    @Test
    fun binaryArtifactImportsRealProfileNotReceipt() {
        val profile = N2Profile.calibrated()
        val bytes = ByteArrayOutputStream().also { N2BinaryArtifact.write(profile,it) }.toByteArray()
        val loaded = N2BinaryArtifact.read(ByteArrayInputStream(bytes))
        assertEquals(profile.identity, loaded.profile.identity)
        assertEquals(13.728409855272066, loaded.profile.sourceScale, 0.0)
        assertEquals(18.2039020043, loaded.profile.eventScale, 0.0)
        assertEquals(64, loaded.artifactSha256.length)
        repeat(N2Profile.BASIS_COUNT){assertArrayEquals(profile.basis(it),loaded.profile.basis(it),0.0)}
        assertArrayEquals(profile.eventResponse(),loaded.profile.eventResponse(),0.0)
    }

    @Test
    fun malformedArtifactIsRejected() {
        val profile=N2Profile.calibrated()
        val bytes=ByteArrayOutputStream().also{N2BinaryArtifact.write(profile,it)}.toByteArray()
        assertThrows(IllegalArgumentException::class.java){N2BinaryArtifact.read(ByteArrayInputStream(bytes.copyOf(bytes.size-3)))}
    }
}
