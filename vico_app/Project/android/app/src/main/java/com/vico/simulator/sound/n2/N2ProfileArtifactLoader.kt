package com.vico.simulator.sound.n2

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

/** Runtime entry point for the frozen artifact. Profiles are loaded, never regenerated. */
internal object N2ProfileArtifactLoader {
    internal data class Loaded(
        val receipt: N2BinaryReceipt,
        val bytes: ByteArray,
    )

    fun export(profile: N2Profile): Loaded {
        val output = ByteArrayOutputStream()
        N2BinaryArtifact.write(profile, output)
        val bytes = output.toByteArray()
        return Loaded(N2BinaryArtifact.read(ByteArrayInputStream(bytes)), bytes)
    }

    fun verify(bytes: ByteArray, expectedIdentity: String): N2BinaryReceipt {
        val receipt = N2BinaryArtifact.read(ByteArrayInputStream(bytes))
        require(receipt.identity == expectedIdentity) { "N2 artifact identity mismatch" }
        require(receipt.sourceScale == 13.728409855272066) { "N2 source calibration drift" }
        return receipt
    }
}
