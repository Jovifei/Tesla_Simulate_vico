package com.vico.simulator.sound.n2.diagnostic

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.n2.N2Mode
import com.vico.simulator.sound.n2.N2Profile
import com.vico.simulator.sound.n2.N2Renderer
import java.io.File
import java.security.MessageDigest
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Opt-in synthetic diagnostic export only.
 *
 * Writes only generated PCM/stems/hashes. It does not read references, credentials,
 * network data, or modify existing output files.
 */
internal object N2SyntheticReferenceExporter {
    private val modes = listOf(
        N2Mode.T to true,
        N2Mode.S to true,
        N2Mode.E to true,
        N2Mode.E to false,
        N2Mode.SE to true,
        N2Mode.SE to false,
    )

    fun export(output: File) {
        require(!output.exists()) { "diagnostic output must be new" }
        output.mkdirs()
        val profile = N2Profile.calibrated()
        val states = steadyFixture()
        val baseline = HybridTestProfiles.create()
        val manifest = StringBuilder()
        modes.forEach { (mode, events) ->
            val renderer = N2Renderer(baseline, profile, mode, true, events)
            val pcm = states.flatMap { renderer.render(it, 960).asList() }.toFloatArray()
            val file = File(output, "${mode}_event_${events}.pcm.f32le")
            file.writeBytes(ByteBuffer.allocate(pcm.size * 4).order(ByteOrder.LITTLE_ENDIAN).apply {
                pcm.forEach(::putFloat)
            }.array())
            manifest.append(file.name).append('\t').append(sha(file)).append('\n')
        }
        File(output, "manifest.tsv").writeText(manifest.toString())
    }

    private fun steadyFixture(): List<SoundState> = List(150) { n ->
        SoundState(
            n * .02,
            4500.0,
            0.0,
            .7,
            .7,
            floatArrayOf(),
            false,
            .7,
            .7,
        )
    }

    private fun sha(file: File): String = MessageDigest.getInstance("SHA-256")
        .digest(file.readBytes()).joinToString("") { "%02x".format(it) }
}
