package com.vico.simulator.sound.n2

import com.vico.simulator.sound.n2.diagnostic.N2QualificationTapBuffer
import com.vico.simulator.sound.s18.C63HybridMode
import com.vico.simulator.sound.s18.C63HybridProfile
import com.vico.simulator.sound.s18.C63HybridRenderer
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.StandardOpenOption.CREATE_NEW
import java.security.MessageDigest
import kotlin.math.abs
import kotlin.math.sqrt

/** Bounded diagnostic measurements of actual imported-artifact renders. No fitting or acceptance. */
internal class N2HistoricalDigitalVerification(baselineArtifact: ByteArray, profileArtifact: ByteArray) {
    private val baseline = C63HybridProfile.fromBytes(baselineArtifact.copyOf())
    private val loaded = N2ProfileArtifactLoader.import(profileArtifact.copyOf())
    val baselineArtifactSha256 = N2QualificationExport.sha(baselineArtifact)
    val artifactSha256 = loaded.artifactSha256
    val baselineIdentity = baseline.identity
    val profileIdentity = loaded.profile.identity

    internal data class Result(
        val fixtureId: String, val fixtureSha256: String, val mode: N2Mode, val eventsAudible: Boolean,
        val frames: Long, val pcmSha256: String, val tapSha256: String,
        val peak: Double, val rendererPeak: Double, val energy: Double, val rms: Double,
        val tapPeaks: List<Double>, val tapEnergies: List<Double>,
        val firstCeilingExceed: Long, val rawArrivals: Long, val impulseFrames: Long,
        val pendingFrames: Int, val observationTruncated: Boolean,
    ) {
        // Nonfinite samples/energy and missing frames reject before this result can be constructed.
        val digitalPass: Boolean get() = firstCeilingExceed < 0 && rendererPeak <= DIGITAL_CEILING && !observationTruncated
    }

    fun render(fixture: N2QualificationFixture, mode: N2Mode, eventsAudible: Boolean,
               partitions: IntArray = intArrayOf(960)): Result {
        validatePartitions(partitions)
        val renderer = N2Renderer(baseline, loaded.profile, mode, true, eventsAudible)
        val capacity = partitions.maxOrNull()!!
        val tap = N2QualificationTapBuffer(capacity)
        val pcmBytes = ByteBuffer.allocate(capacity * 4).order(ByteOrder.LITTLE_ENDIAN)
        val tapBytes = ByteBuffer.allocate(capacity * 9 * 8).order(ByteOrder.LITTLE_ENDIAN)
        val pcmHash = MessageDigest.getInstance("SHA-256"); val tapHash = MessageDigest.getInstance("SHA-256")
        val tapPeaks = DoubleArray(9); val tapEnergies = DoubleArray(9)
        var frames = 0L; var peak = 0.0; var energy = 0.0; var firstExceed = -1L
        chunks(fixture, partitions) { segment, count ->
            tap.reset()
            val pcm = renderer.render(segment.state, count, segment.validInput, tap)
            val observed = tap.copyFrames()
            check(pcm.size == count && observed.size == count)
            pcmBytes.clear(); tapBytes.clear()
            for (i in 0 until count) {
                val sample = pcm[i].toDouble()
                check(sample.isFinite()) { "Nonfinite PCM at ${frames + i}" }
                peak = maxOf(peak, abs(sample)); energy += sample * sample
                if (firstExceed < 0 && abs(sample) > DIGITAL_CEILING) firstExceed = frames + i
                pcmBytes.putFloat(pcm[i])
                observed[i].forEachIndexed { channel, value ->
                    check(value.isFinite()) { "Nonfinite tap at ${frames + i}/$channel" }
                    tapPeaks[channel] = maxOf(tapPeaks[channel], abs(value))
                    tapEnergies[channel] += value * value
                    tapBytes.putDouble(value)
                }
            }
            check(energy.isFinite() && tapEnergies.all { it.isFinite() }) { "Nonfinite accumulated energy" }
            pcmHash.update(pcmBytes.array(), 0, count * 4)
            tapHash.update(tapBytes.array(), 0, count * 9 * 8)
            frames += count
        }
        check(frames == fixture.frames.toLong() && frames == renderer.frames)
        val events = renderer.eventObservation()
        return Result(fixture.id, fixture.sha256, mode, eventsAudible, frames, hex(pcmHash.digest()), hex(tapHash.digest()),
            peak, renderer.peak, energy, sqrt(energy / frames), tapPeaks.toList(), tapEnergies.toList(), firstExceed,
            events.rawArrivals, events.distinctImpulseFrames, renderer.pendingFrames, events.truncated)
    }

    /** Separately scoped exact frozen-T comparison; does not imply acoustic/reference equivalence. */
    fun verifyFrozenT(fixture: N2QualificationFixture, partitions: IntArray = intArrayOf(960)): Long {
        validatePartitions(partitions)
        val control = C63HybridRenderer(baseline, C63HybridMode.T, true, true)
        val n2 = N2Renderer(baseline, loaded.profile, N2Mode.T, true, true)
        var frames = 0L
        chunks(fixture, partitions) { segment, count ->
            val expected = control.render(segment.state, count, segment.validInput)
            val actual = n2.render(segment.state, count, segment.validInput)
            check(expected.contentEquals(actual)) { "Frozen T mismatch in ${fixture.id} after $frames frames" }
            frames += count
        }
        check(frames == fixture.frames.toLong())
        return frames
    }

    companion object {
        const val DIGITAL_CEILING = .8413951416451951
        val REPRESENTATIVE_IDS: List<String> get() = listOf(
            "Q0_steady_700.0_0.0", "Q0_transition_7200.0_700.0", "Q1_original", "Q2_540.0_2",
            "Q3_hot_events", "Q3_restart_0", "Q4_1849.0_0.32_0.35_true", "H2_0.12_true", "H3_events",
        )
        private fun validatePartitions(partitions: IntArray) {
            require(partitions.isNotEmpty() && partitions.all { it in 1..4800 })
        }
        private fun chunks(fixture: N2QualificationFixture, partitions: IntArray,
                           block: (N2TrajectorySegment, Int) -> Unit) {
            var partitionIndex = 0
            fixture.segments().forEach { segment ->
                var remaining = segment.frames
                while (remaining > 0) {
                    val count = minOf(partitions[partitionIndex], remaining)
                    partitionIndex = (partitionIndex + 1) % partitions.size
                    block(segment, count); remaining -= count
                }
            }
        }
        private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }

        /** Explicit opt-in CLI: inputs are never generated or silently substituted here. */
        @JvmStatic fun main(args: Array<String>) {
            require(args.size == 5 && args[4] in listOf("representative", "all-available")) {
                "usage: ORIGINAL_TRACE_JSON BASELINE_ARTIFACT N2_ARTIFACT NEW_OUTPUT_DIR representative|all-available"
            }
            val catalog = N2HistoricalStateCatalog(File(args[0]).readBytes())
            val verifier = N2HistoricalDigitalVerification(File(args[1]).readBytes(), File(args[2]).readBytes())
            val selected = if (args[4] == "all-available") catalog.available else REPRESENTATIVE_IDS.map(catalog::entry)
            val root = File(args[3]).toPath()
            Files.createDirectory(root)
            Files.write(root.resolve("catalog.tsv"), catalog.bytes(), CREATE_NEW)
            val results = StringBuilder("id\tfixture_sha256\tmode\tevents_audible\tframes\tpcm_sha256\ttaps_sha256\tpeak\trenderer_peak\tenergy\trms\ttap_peaks\ttap_energies\tfirst_ceiling_exceed\traw_arrivals\timpulse_frames\tpending_frames\tobservation_truncated\tdigital_pass\n")
            var pass = 0
            selected.forEach { entry ->
                val fixture = entry.fixture()
                N2QualificationExport.branches.forEach { (mode, audible) ->
                    val r = verifier.render(fixture, mode, audible)
                    if (r.digitalPass) pass++
                    results.append(listOf(r.fixtureId, r.fixtureSha256, r.mode, r.eventsAudible, r.frames,
                        r.pcmSha256, r.tapSha256, r.peak, r.rendererPeak, r.energy, r.rms,
                        r.tapPeaks.joinToString(","), r.tapEnergies.joinToString(","), r.firstCeilingExceed,
                        r.rawArrivals, r.impulseFrames, r.pendingFrames, r.observationTruncated, r.digitalPass).joinToString("\t")).append('\n')
                }
                println("Measured ${entry.id}: ${entry.frames} frames per branch")
            }
            val resultBytes = results.toString().toByteArray(Charsets.UTF_8)
            Files.write(root.resolve("digital-results.tsv"), resultBytes, CREATE_NEW)
            val receipt = """
                schema\tc63.n2.historical_digital_receipt.v1
                status\tREFERENCE_FREE_DIGITAL_MEASUREMENT_NOT_ACOUSTIC_QUALIFICATION
                catalog_sha256\t${catalog.sha256}
                baseline_artifact_sha256\t${verifier.baselineArtifactSha256}
                n2_artifact_sha256\t${verifier.artifactSha256}
                baseline_identity\t${verifier.baselineIdentity}
                profile_identity\t${verifier.profileIdentity}
                input_inventory_cases\t630
                available_cases\t338
                missing_input_cases\t292
                selected_cases\t${selected.size}
                rendered_branches_per_case\t6
                frames_per_branch\t${selected.sumOf { it.frames!!.toLong() }}
                digital_passes\t$pass
                digital_failures\t${selected.size * 6 - pass}
                partitions\t960
                digital_ceiling\t$DIGITAL_CEILING
                results_sha256\t${N2QualificationExport.sha(resultBytes)}
                partition_equivalence_scope\tNOT_RUN_BY_THIS_CLI
                frozen_T_scope\tNOT_RUN_BY_THIS_CLI
                snapshot_scope\tNOT_RUN_BY_THIS_CLI
                full_630_case_qualification\tNOT_RUN_MISSING_INPUTS_AND_REFERENCE_GATES
            """.trimIndent().replace("\\t", "\t") + "\n"
            Files.write(root.resolve("receipt.tsv"), receipt.toByteArray(Charsets.UTF_8), CREATE_NEW)
            println(receipt)
            check(pass == selected.size * 6) { "Digital failure recorded; frozen gains remain unchanged" }
        }
    }
}
