package com.vico.simulator.sound.n2

import com.vico.simulator.sound.n2.diagnostic.N2SyntheticReferenceExporter
import java.io.File
import org.junit.Assume
import org.junit.Test

/** Opt-in export using explicit artifact files. Missing inputs are a skip, never qualification. */
class N2PcmFixtureTest {
    @Test
    fun exportSixControlledBranchesForLocalReferenceComputation() {
        val destination = System.getenv("VICO_C63_N2_FIXTURE_OUTPUT")
        Assume.assumeTrue(!destination.isNullOrBlank())
        val baseline = requireNotNull(System.getenv("VICO_C63_BASELINE_ARTIFACT"))
        val profile = requireNotNull(System.getenv("VICO_C63_N2_ARTIFACT"))
        val partitions = (System.getenv("VICO_C63_N2_PARTITIONS") ?: "960")
            .split(',').map(String::toInt).toIntArray()
        N2SyntheticReferenceExporter.export(File(requireNotNull(destination)),
            File(baseline).readBytes(), File(profile).readBytes(), partitions)
    }
}
