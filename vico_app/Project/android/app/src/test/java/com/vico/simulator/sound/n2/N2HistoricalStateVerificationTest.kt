package com.vico.simulator.sound.n2

import com.vico.simulator.sound.HybridTestProfiles
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.FileAlreadyExistsException
import java.nio.file.Files

class N2HistoricalStateVerificationTest {
    private val baseline get() = HybridTestProfiles.create().toBytes()
    private val artifact get() = N2ProfileArtifactLoader.export(N2Profile.calibrated()).bytes
    private fun verifier() = N2HistoricalDigitalVerification(baseline, artifact)

    @Test fun completeEventCaseChecksAllSixBranchPairsAndIndependentFrozenT() {
        val fixture = N2HistoricalStateCatalog.fromCheckedInTrace().entry("H3_events").fixture()
        val result = N2HistoricalStateVerification.verifyFixture(verifier(), fixture)
        assertEquals(fixture.id, result.fixtureId)
        assertEquals(fixture.sha256, result.fixtureSha256)
        assertEquals(fixture.frames.toLong(), result.frames)
        assertEquals(result.frames, result.frozenTFrames)
        assertEquals(N2QualificationExport.branches, result.branches.map { it.block.mode to it.block.eventsAudible })
        assertTrue(result.passed)
        assertTrue(result.branches.all { it.partitionExactMatch && it.digitalPass })
        assertFalse(result.copy(branches = result.branches.dropLast(1)).passed)
        assertFalse(result.copy(branches = List(6) { result.branches.first() }).passed)
        assertFalse(result.copy(frozenTFrames = result.frames - 1).passed)
    }

    @Test fun branchInventoryRejectsMissingDuplicateReorderedAndChangedIdentities() {
        val expected = N2QualificationExport.branches
        N2HistoricalStateVerification.requireControlledBranches(expected)
        for (changed in listOf(expected.dropLast(1), expected + expected.first(), expected.reversed(),
            expected.dropLast(1) + expected.first(), listOf(N2Mode.T to false) + expected.drop(1))) {
            assertThrows(IllegalArgumentException::class.java) { N2HistoricalStateVerification.requireControlledBranches(changed) }
        }
    }

    @Test fun comparisonsRejectIdentityDriftAndObserveEveryResultField() {
        val points = N2HistoricalStateCatalog.fromCheckedInTrace().entry("H3_events").fixture().segments().take(2)
        val result = verifier().render(N2QualificationFixture("state-comparison-test", points), N2Mode.T, true)
        fun pair(other: N2HistoricalDigitalVerification.Result) = N2HistoricalStateVerification.BranchPair(result, other)
        assertTrue(pair(result.copy()).partitionExactMatch)
        for (changed in listOf(result.copy(pcmSha256 = "0".repeat(64)), result.copy(tapSha256 = "0".repeat(64)),
            result.copy(peak = result.peak + 1), result.copy(rendererPeak = result.rendererPeak + 1),
            result.copy(firstCeilingExceed = 0),
            result.copy(energy = result.energy + 1), result.copy(rms = result.rms + 1),
            result.copy(tapPeaks = result.tapPeaks.map { it + 1 }), result.copy(tapEnergies = result.tapEnergies.map { it + 1 }),
            result.copy(rawArrivals = result.rawArrivals + 1), result.copy(impulseFrames = result.impulseFrames + 1),
            result.copy(pendingFrames = result.pendingFrames + 1), result.copy(observationTruncated = true))) {
            assertFalse(pair(changed).partitionExactMatch)
        }
        for (changed in listOf(result.copy(fixtureId = "different"), result.copy(fixtureSha256 = "0".repeat(64)),
            result.copy(mode = N2Mode.S), result.copy(eventsAudible = false), result.copy(frames = result.frames + 1))) {
            assertThrows(IllegalArgumentException::class.java) { pair(changed) }
        }
        val unsafe = result.copy(firstCeilingExceed = 0)
        val equalUnsafe = N2HistoricalStateVerification.BranchPair(unsafe, unsafe.copy())
        assertTrue(equalUnsafe.partitionExactMatch)
        assertFalse(equalUnsafe.digitalPass)
        assertFalse(pair(result.copy(rendererPeak = 1.0)).digitalPass)
    }

    @Test fun schedulesAreExplicitDistinctAndCannotBeMutatedByCallers() {
        assertArrayEquals(intArrayOf(960), N2HistoricalStateVerification.blockPartitions)
        assertArrayEquals(intArrayOf(333, 297), N2HistoricalStateVerification.splitPartitions)
        assertArrayEquals(intArrayOf(17, 333, 71, 960, 5, 241), N2HistoricalStateVerification.frozenTPartitions)
        N2HistoricalStateVerification.blockPartitions.fill(1)
        N2HistoricalStateVerification.splitPartitions.fill(960)
        N2HistoricalStateVerification.frozenTPartitions.fill(960)
        assertArrayEquals(intArrayOf(960), N2HistoricalStateVerification.blockPartitions)
        assertArrayEquals(intArrayOf(333, 297), N2HistoricalStateVerification.splitPartitions)
        assertEquals(17, N2HistoricalStateVerification.frozenTPartitions.first())
    }

    @Test fun cliRejectsUnknownSelectionAndNeverOverwritesAnExistingOutput() {
        assertThrows(IllegalArgumentException::class.java) { N2HistoricalStateVerification.main(emptyArray()) }
        assertThrows(IllegalArgumentException::class.java) {
            N2HistoricalStateVerification.main(arrayOf("trace", "baseline", "profile", "out", "all-630"))
        }
        val temp = Files.createTempDirectory("n2-state-cli-contract-")
        try {
            val base = temp.resolve("baseline.bin"); val profile = temp.resolve("profile.bin")
            Files.write(base, baseline); Files.write(profile, artifact)
            val output = Files.createDirectory(temp.resolve("existing"))
            val sentinel = output.resolve("keep.txt"); Files.write(sentinel, byteArrayOf(1, 2, 3))
            assertThrows(FileAlreadyExistsException::class.java) {
                N2HistoricalStateVerification.main(arrayOf(N2HistoricalStateCatalog.checkedInTraceFile().absolutePath,
                    base.toString(), profile.toString(), output.toString(), "representative"))
            }
            assertArrayEquals(byteArrayOf(1, 2, 3), Files.readAllBytes(sentinel))
            Files.list(output).use { assertEquals(1L, it.count()) }
        } finally {
            Files.walk(temp).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach { Files.delete(it) } }
        }
    }
}
