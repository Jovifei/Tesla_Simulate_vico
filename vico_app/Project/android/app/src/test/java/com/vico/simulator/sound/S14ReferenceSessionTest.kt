package com.vico.simulator.sound

import java.nio.file.Files
import java.nio.file.Paths
import org.junit.Assert.assertEquals
import org.junit.Assume.assumeTrue
import org.junit.Test

class S14ReferenceSessionTest {
    @Test(expected = IllegalArgumentException::class)
    fun truncated_reference_is_rejected() { S14ReferenceSession(ByteArray(8), "R") }

    @Test(expected = IllegalArgumentException::class)
    fun wrong_reference_hash_is_rejected() {
        S14ReferenceSession(ByteArray(S13ReviewContract.TOTAL_FRAMES * 4), "M")
    }

    @Test fun originals_emit_exactly_once_without_gain_or_envelope() {
        val root = System.getenv("VICO_S14_REFERENCE_ROOT")
        assumeTrue("Provide SHA-bound S14 references", !root.isNullOrEmpty())
        for (label in listOf("R", "M")) {
            val original = Files.readAllBytes(Paths.get(root!!).resolve("$label.f32le"))
            val session = S14ReferenceSession(original, label)
            val output = java.io.ByteArrayOutputStream()
            while (!session.isComplete) {
                val pcm = session.renderNext()!!
                val buffer = java.nio.ByteBuffer.allocate(pcm.size * 4).order(java.nio.ByteOrder.LITTLE_ENDIAN)
                pcm.forEach(buffer::putFloat)
                output.write(buffer.array())
            }
            assertEquals(S13ReviewContract.TOTAL_FRAMES, session.framesRendered)
            assertEquals(session.expectedSha, S13ReviewContract.sha256(output.toByteArray()))
            assertEquals(null, session.renderNext())
        }
    }
}
