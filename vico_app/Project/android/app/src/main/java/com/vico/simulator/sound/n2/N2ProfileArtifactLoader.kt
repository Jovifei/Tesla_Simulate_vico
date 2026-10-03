package com.vico.simulator.sound.n2

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

/** The runtime entry point returns the immutable loaded profile, not a receipt. */
internal object N2ProfileArtifactLoader {
    internal data class Loaded(
        val profile: N2Profile,
        val artifactSha256: String,
        val bytes: ByteArray,
    )

    fun export(profile: N2Profile): Loaded {
        val out = ByteArrayOutputStream()
        N2BinaryArtifact.write(profile, out)
        val bytes = out.toByteArray()
        val loaded = N2BinaryArtifact.read(ByteArrayInputStream(bytes))
        require(loaded.profile.identity == profile.identity)
        return Loaded(loaded.profile, loaded.artifactSha256, bytes)
    }

    fun import(bytes: ByteArray): Loaded {
        val loaded = N2BinaryArtifact.read(ByteArrayInputStream(bytes))
        return Loaded(loaded.profile, loaded.artifactSha256, bytes.copyOf())
    }
}
