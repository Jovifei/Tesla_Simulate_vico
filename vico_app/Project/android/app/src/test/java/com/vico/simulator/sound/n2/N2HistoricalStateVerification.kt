package com.vico.simulator.sound.n2

import java.io.File
import java.nio.file.Files
import java.nio.file.StandardOpenOption.CREATE_NEW

/** Explicit artifact-bound state diagnostics. No production routing, fitting or reference scoring. */
internal object N2HistoricalStateVerification {
    private const val BRANCH_COUNT = 6
    private val expectedBranches get() = listOf(
        N2Mode.T to true, N2Mode.S to true, N2Mode.E to true,
        N2Mode.E to false, N2Mode.SE to true, N2Mode.SE to false,
    )
    val blockPartitions get() = intArrayOf(960)
    val splitPartitions get() = intArrayOf(333, 297)
    val frozenTPartitions get() = intArrayOf(17, 333, 71, 960, 5, 241)

    internal data class BranchPair(
        val block: N2HistoricalDigitalVerification.Result,
        val split: N2HistoricalDigitalVerification.Result,
    ) {
        init {
            require(block.fixtureId == split.fixtureId && block.fixtureSha256 == split.fixtureSha256 &&
                block.mode == split.mode && block.eventsAudible == split.eventsAudible && block.frames == split.frames) {
                "Partition comparison requires the same fixture, branch and frame count"
            }
        }
        // Equality includes PCM/tap hashes and every metric/counter retained by Result.
        // Full event episodes and arrival/impulse arrays are not retained by this diagnostic.
        val partitionExactMatch: Boolean get() = block == split
        val digitalPass: Boolean get() = block.digitalPass && split.digitalPass
    }

    internal data class CaseResult(
        val fixtureId: String,
        val fixtureSha256: String,
        val frames: Long,
        val frozenTFrames: Long,
        val branches: List<BranchPair>,
    ) {
        val passed: Boolean get() = frozenTFrames == frames && branches.size == BRANCH_COUNT &&
            branches.map { it.block.mode to it.block.eventsAudible } == expectedBranches &&
            branches.all { it.partitionExactMatch && it.digitalPass }
    }

    fun requireControlledBranches(branches: List<Pair<N2Mode, Boolean>>) {
        require(branches == expectedBranches) { "Expected the six frozen ordered controlled branch identities" }
    }

    fun verifyFixture(verifier: N2HistoricalDigitalVerification, fixture: N2QualificationFixture): CaseResult {
        val branches = N2QualificationExport.branches
        requireControlledBranches(branches)
        // Fail immediately on frozen-T identity drift; never fit or change the baseline.
        val frozen = verifier.verifyFrozenT(fixture, frozenTPartitions)
        val pairs = branches.map { (mode, audible) ->
            BranchPair(verifier.render(fixture, mode, audible, blockPartitions),
                verifier.render(fixture, mode, audible, splitPartitions))
        }
        return CaseResult(fixture.id, fixture.sha256, fixture.frames.toLong(), frozen, pairs)
    }

    @JvmStatic fun main(args: Array<String>) {
        require(args.size == 5 && args[4] in listOf("representative", "all-available")) {
            "usage: ORIGINAL_TRACE_JSON BASELINE_ARTIFACT N2_ARTIFACT NEW_OUTPUT_DIR representative|all-available"
        }
        val catalog = N2HistoricalStateCatalog(File(args[0]).readBytes())
        val verifier = N2HistoricalDigitalVerification(File(args[1]).readBytes(), File(args[2]).readBytes())
        val selected = if (args[4] == "all-available") catalog.available else
            N2HistoricalDigitalVerification.REPRESENTATIVE_IDS.map(catalog::entry)
        val root = Files.createDirectory(File(args[3]).toPath())
        Files.write(root.resolve("catalog.tsv"), catalog.bytes(), CREATE_NEW)
        val states = StringBuilder("id\tfixture_sha256\tmode\tevents_audible\tframes\tblock_pcm_sha256\tsplit_pcm_sha256\tblock_taps_sha256\tsplit_taps_sha256\tblock_peak\tsplit_peak\tblock_renderer_peak\tsplit_renderer_peak\tblock_digital_pass\tsplit_digital_pass\tpartition_exact_match\n")
        val frozenT = StringBuilder("id\tfixture_sha256\tframes\tfrozen_T_equal_frames\n")
        var partitionPasses = 0
        var digitalPasses = 0
        var frozenTFrames = 0L
        selected.forEach { entry ->
            val r = verifyFixture(verifier, entry.fixture())
            check(r.frozenTFrames == r.frames)
            frozenTFrames += r.frozenTFrames
            frozenT.append(listOf(r.fixtureId, r.fixtureSha256, r.frames, r.frozenTFrames).joinToString("\t")).append('\n')
            r.branches.forEach { pair ->
                val a = pair.block; val b = pair.split
                if (pair.partitionExactMatch) partitionPasses++
                if (a.digitalPass) digitalPasses++
                if (b.digitalPass) digitalPasses++
                states.append(listOf(a.fixtureId, a.fixtureSha256, a.mode, a.eventsAudible, a.frames,
                    a.pcmSha256, b.pcmSha256, a.tapSha256, b.tapSha256, a.peak, b.peak, a.rendererPeak,
                    b.rendererPeak, a.digitalPass, b.digitalPass, pair.partitionExactMatch).joinToString("\t")).append('\n')
            }
            println("State-checked ${entry.id}: ${r.frames} frames, six partition comparisons, frozen T")
        }
        val stateBytes = states.toString().toByteArray(Charsets.UTF_8)
        val frozenBytes = frozenT.toString().toByteArray(Charsets.UTF_8)
        Files.write(root.resolve("partition-results.tsv"), stateBytes, CREATE_NEW)
        Files.write(root.resolve("frozen-t-results.tsv"), frozenBytes, CREATE_NEW)
        val expectedPairs = selected.size * BRANCH_COUNT
        val receipt = """
            schema\tc63.n2.historical_state_receipt.v1
            status\tREFERENCE_FREE_STATE_DIAGNOSTICS_NOT_ACOUSTIC_QUALIFICATION
            catalog_sha256\t${catalog.sha256}
            baseline_artifact_sha256\t${verifier.baselineArtifactSha256}
            n2_artifact_sha256\t${verifier.artifactSha256}
            baseline_identity\t${verifier.baselineIdentity}
            profile_identity\t${verifier.profileIdentity}
            input_inventory_cases\t630
            available_cases\t338
            missing_input_cases\t292
            selected_cases\t${selected.size}
            branches_per_case\t6
            frames_per_branch\t${selected.sumOf { it.frames!!.toLong() }}
            block_partitions\t${blockPartitions.joinToString(",")}
            split_partitions\t${splitPartitions.joinToString(",")}
            partition_exact_passes\t$partitionPasses
            partition_exact_failures\t${expectedPairs - partitionPasses}
            digital_passes\t$digitalPasses
            digital_failures\t${expectedPairs * 2 - digitalPasses}
            digital_ceiling\t${N2HistoricalDigitalVerification.DIGITAL_CEILING}
            frozen_T_partitions\t${frozenTPartitions.joinToString(",")}
            frozen_T_equal_cases\t${selected.size}
            frozen_T_equal_frames\t$frozenTFrames
            partition_results_sha256\t${N2QualificationExport.sha(stateBytes)}
            frozen_T_results_sha256\t${N2QualificationExport.sha(frozenBytes)}
            snapshot_scope\tNOT_RUN_BY_THIS_CLI
            arbitrary_partition_scope\tNOT_PROVEN
            full_630_case_qualification\tNOT_RUN_MISSING_INPUTS_AND_REFERENCE_GATES
        """.trimIndent().replace("\\t", "\t") + "\n"
        Files.write(root.resolve("receipt.tsv"), receipt.toByteArray(Charsets.UTF_8), CREATE_NEW)
        println(receipt)
        check(partitionPasses == expectedPairs && digitalPasses == expectedPairs * 2) {
            "State/digital failure recorded; frozen parameters remain unchanged"
        }
    }
}
