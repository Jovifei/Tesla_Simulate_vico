package com.vico.simulator.sound.n2

import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.n2.diagnostic.N2QualificationTapBuffer
import com.vico.simulator.sound.s18.C63HybridProfile
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.StandardOpenOption.CREATE_NEW
import java.security.MessageDigest

/** One piecewise-constant input segment; render partitions never move its input boundary. */
internal data class N2TrajectorySegment(val state: SoundState, val frames: Int, val validInput: Boolean = true)

/** Owns a frozen copy of the entire input, including fields the current renderer does not consume. */
internal class N2QualificationFixture(val id: String, segments: List<N2TrajectorySegment>) {
    private val input = segments.map { it.copy(state = it.state.copy(harmonics = it.state.harmonics.copyOf())) }
    val frames: Int
    val sha256: String
    private val encoded: ByteArray

    init {
        require(id.matches(Regex("[A-Za-z0-9_.-]{1,120}")))
        require(input.isNotEmpty()) { "Empty trajectories cannot produce qualification evidence" }
        frames = input.fold(0) { total, segment ->
            val s = segment.state
            require(segment.frames > 0)
            require(s.timeS.isFinite() && s.rpm.isFinite() && s.rpm in 0.0..7200.0 &&
                s.load.isFinite() && s.load in 0.0..1.0 && s.throttle.isFinite() && s.throttle in 0.0..1.0)
            require(s.frequencyHz.isFinite() && s.amplitude.isFinite() && s.brightness.isFinite() &&
                s.shiftGain.isFinite() && s.harmonics.all { it.isFinite() })
            Math.addExact(total, segment.frames)
        }
        encoded = ByteArrayOutputStream().also { bytes ->
            DataOutputStream(bytes).use { out ->
                out.writeUTF("c63.n2.trajectory.v1")
                out.writeUTF(id)
                out.writeInt(input.size)
                input.forEach { segment ->
                    val s = segment.state
                    out.writeInt(segment.frames); out.writeBoolean(segment.validInput)
                    for (value in doubleArrayOf(s.timeS, s.rpm, s.frequencyHz, s.amplitude, s.brightness,
                        s.throttle, s.load, s.shiftGain)) out.writeDouble(value)
                    out.writeInt(s.harmonics.size); s.harmonics.forEach(out::writeFloat)
                    out.writeBoolean(s.muted); out.writeBoolean(s.braking); out.writeInt(s.gear)
                    out.writeBoolean(s.afterfireTrigger); out.writeBoolean(s.shiftTrigger)
                }
            }
        }.toByteArray()
        sha256 = N2QualificationExport.sha(encoded)
    }

    fun bytes() = encoded.copyOf()
    fun segments() = input.map { it.copy(state = it.state.copy(harmonics = it.state.harmonics.copyOf())) }
}

internal data class N2RenderExport(
    val candidateId: String,
    val mode: N2Mode,
    val eventsAudible: Boolean,
    val sampleRate: Int,
    val channels: Int,
    val frames: Int,
    val profileIdentity: String,
    val artifactSha256: String,
    val baselineIdentity: String,
    val baselineArtifactSha256: String,
    val fixtureId: String,
    val fixtureSha256: String,
    val measurement: N2Measurement.Result,
    val pcm: FloatArray,
    val sourceTaps: Array<DoubleArray>,
    val eventObservation: N2Source.EventObservation,
    val pendingFrames: Int,
)

/** Offline qualification export only. No default profile generation or runtime sound-bank routing. */
internal object N2QualificationExport {
    val branches: List<Pair<N2Mode, Boolean>> get() = listOf(
        N2Mode.T to true, N2Mode.S to true, N2Mode.E to true,
        N2Mode.E to false, N2Mode.SE to true, N2Mode.SE to false,
    )

    fun renderAll(
        fixture: N2QualificationFixture,
        baselineArtifact: ByteArray,
        profileArtifact: ByteArray,
        partitions: IntArray = intArrayOf(960),
    ): List<N2RenderExport> {
        val prepared = prepare(baselineArtifact, profileArtifact, partitions)
        return branches.map { (mode, audible) -> render(fixture, prepared, mode, audible) }
    }

    private data class Prepared(
        val baseline: C63HybridProfile,
        val loaded: N2ProfileArtifactLoader.Loaded,
        val baselineBytes: ByteArray,
        val partitions: IntArray,
    )

    private fun prepare(baseline: ByteArray, artifact: ByteArray, partitions: IntArray): Prepared {
        require(partitions.isNotEmpty() && partitions.all { it in 1..4800 })
        val baselineBytes = baseline.copyOf()
        return Prepared(C63HybridProfile.fromBytes(baselineBytes),
            N2ProfileArtifactLoader.import(artifact.copyOf()), baselineBytes, partitions.copyOf())
    }

    private fun render(
        fixture: N2QualificationFixture,
        prepared: Prepared,
        mode: N2Mode,
        eventsAudible: Boolean,
    ): N2RenderExport {
        val renderer = N2Renderer(prepared.baseline, prepared.loaded.profile, mode,
            qualificationOnly = true, eventsAudible = eventsAudible)
        val pcm = FloatArray(fixture.frames)
        val tap = N2QualificationTapBuffer(fixture.frames)
        var offset = 0
        var partitionIndex = 0
        fixture.segments().forEach { segment ->
            var remaining = segment.frames
            while (remaining > 0) {
                val count = minOf(prepared.partitions[partitionIndex], remaining)
                partitionIndex = (partitionIndex + 1) % prepared.partitions.size
                // Copy immediately: the renderer intentionally reuses its 960-frame buffer.
                renderer.render(segment.state, count, segment.validInput, tap).copyInto(pcm, offset)
                offset += count
                remaining -= count
            }
        }
        val measurement = N2Measurement.measure(pcm)
        check(measurement.evidenceValid && tap.frameCount() == pcm.size)
        check(!renderer.eventObservation().truncated) { "N2 event observation capacity exceeded" }
        return N2RenderExport(renderer.candidateId, mode, eventsAudible, N2Profile.SAMPLE_RATE, 1,
            pcm.size, prepared.loaded.profile.identity, prepared.loaded.artifactSha256,
            prepared.baseline.identity, sha(prepared.baselineBytes), fixture.id, fixture.sha256,
            measurement, pcm, tap.copyFrames(), renderer.eventObservation(), renderer.pendingFrames)
    }

    /** Creates a new destination atomically; completion receipt is written last. Never overwrites. */
    fun write(
        output: File,
        fixture: N2QualificationFixture,
        baselineArtifact: ByteArray,
        profileArtifact: ByteArray,
        partitions: IntArray = intArrayOf(960),
    ): String {
        require(!Files.exists(output.toPath(), java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
            "qualification output must be new"
        }
        val prepared = prepare(baselineArtifact, profileArtifact, partitions)
        Files.createDirectory(output.toPath())
        fun save(name: String, bytes: ByteArray) {
            Files.write(File(output, name).toPath(), bytes, CREATE_NEW)
        }
        save("profile.bin", prepared.loaded.bytes)
        save("baseline.bin", prepared.baselineBytes)
        save("trajectory.bin", fixture.bytes())
        val receipt = StringBuilder()
        receipt.append("schema\tc63.n2.render_receipt.v1\n")
        receipt.append("status\tRENDERED_ONLY_NOT_ACOUSTIC_QUALIFICATION\n")
        receipt.append("profile_identity\t${prepared.loaded.profile.identity}\n")
        receipt.append("artifact_sha256\t${prepared.loaded.artifactSha256}\n")
        receipt.append("baseline_identity\t${prepared.baseline.identity}\n")
        receipt.append("baseline_artifact_sha256\t${sha(prepared.baselineBytes)}\n")
        receipt.append("fixture_id\t${fixture.id}\nfixture_sha256\t${fixture.sha256}\n")
        receipt.append("sample_rate\t48000\nframes\t${fixture.frames}\n")
        receipt.append("partitions\t${prepared.partitions.joinToString(",")}\n")
        receipt.append("tap_stage\tsource_before_delay_idle_shift_output_headroom\n")
        receipt.append("tap_channels\t${N2QualificationTapBuffer.CHANNEL_NAMES.joinToString(",")}\n")
        receipt.append("file\tsha256\tbytes\tcandidate\tmode\tevents_audible\trms\tpeak\traw_arrivals\timpulse_frames\tpending_frames\n")
        branches.forEach { (mode, audible) ->
            val result = render(fixture, prepared, mode, audible)
            val stem = mode.name.lowercase() + "_event_" + if (audible) "on" else "off"
            val files = listOf(
                "$stem.pcm.f32le" to pcmBytes(result.pcm),
                "$stem.taps.f64le" to tapBytes(result.sourceTaps),
            )
            files.forEach { (name, bytes) ->
                save(name, bytes)
                receipt.append(listOf(name, sha(bytes), bytes.size, result.candidateId, mode, audible,
                    result.measurement.rms, result.measurement.peak, result.eventObservation.rawArrivals,
                    result.eventObservation.distinctImpulseFrames, result.pendingFrames).joinToString("\t")).append('\n')
            }
        }
        val bytes = receipt.toString().toByteArray(Charsets.UTF_8)
        save("manifest.tsv", bytes)
        return sha(bytes)
    }

    fun pcmBytes(pcm: FloatArray): ByteArray = ByteBuffer.allocate(Math.multiplyExact(pcm.size, 4))
        .order(ByteOrder.LITTLE_ENDIAN).apply { pcm.forEach(::putFloat) }.array()

    fun tapBytes(taps: Array<DoubleArray>): ByteArray =
        ByteBuffer.allocate(Math.multiplyExact(taps.size, N2QualificationTapBuffer.CHANNEL_COUNT * 8))
            .order(ByteOrder.LITTLE_ENDIAN).apply {
                taps.forEach { frame ->
                    require(frame.size == N2QualificationTapBuffer.CHANNEL_COUNT)
                    frame.forEach(::putDouble)
                }
            }.array()

    fun sha(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }
}
