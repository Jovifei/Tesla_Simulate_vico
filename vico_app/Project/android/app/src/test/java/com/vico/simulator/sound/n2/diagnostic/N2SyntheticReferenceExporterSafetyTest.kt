package com.vico.simulator.sound.n2.diagnostic

import com.vico.simulator.sound.HybridTestProfiles
import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.n2.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import org.junit.Assert.*
import org.junit.Test

class N2SyntheticReferenceExporterSafetyTest {
    private val baseline get() = HybridTestProfiles.create().toBytes()
    private val artifact get() = N2ProfileArtifactLoader.export(N2Profile.calibrated()).bytes

    @Test fun existingDiagnosticFolderIsRejectedWithoutChangingAnyBytes() {
        val folder = Files.createTempDirectory("n2-export-existing").toFile()
        try {
            val sentinel = File(folder, "t_event_on.pcm.f32le").also { it.writeText("keep") }
            assertThrows(IllegalArgumentException::class.java) {
                N2SyntheticReferenceExporter.export(folder, baseline, artifact)
            }
            assertEquals("keep", sentinel.readText()); assertEquals(1, folder.list()!!.size)
        } finally { folder.deleteRecursively() }
    }

    @Test fun diskReceiptBindsActualPcmAllTapsAndExactImportedArtifacts() {
        val parent = Files.createTempDirectory("n2-export-receipt").toFile()
        try {
            val output = File(parent, "new")
            val bytes = artifact; val base = baseline
            val f = N2QualificationFixture("disk-test", listOf(N2TrajectorySegment(
                SoundState(0.0, 4000.0, 0.0, .9, .9, floatArrayOf(), false, .9, .9), 1920)))
            val hash = N2QualificationExport.write(output, f, base, bytes, intArrayOf(333, 297))
            val manifest = File(output, "manifest.tsv")
            assertEquals(hash, N2QualificationExport.sha(manifest.readBytes()))
            assertArrayEquals(bytes, File(output, "profile.bin").readBytes())
            assertArrayEquals(base, File(output, "baseline.bin").readBytes())
            assertArrayEquals(f.bytes(), File(output, "trajectory.bin").readBytes())
            val lines = manifest.readLines()
            assertTrue(lines.contains("artifact_sha256\t${N2QualificationExport.sha(bytes)}"))
            assertTrue(lines.contains("fixture_sha256\t${f.sha256}"))
            assertTrue(lines.contains("partitions\t333,297"))
            assertEquals(16, output.list()!!.size)
            val renders = N2QualificationExport.renderAll(f, base, bytes, intArrayOf(333, 297))
            val rows = lines.dropWhile { !it.startsWith("file\t") }.drop(1).map { it.split('\t') }
            assertEquals(12, rows.size)
            rows.forEach { row ->
                val actual = File(output, row[0]).readBytes()
                assertEquals(row[1], N2QualificationExport.sha(actual))
                assertEquals(row[2].toInt(), actual.size)
            }
            renders.forEach { render ->
                val prefix = render.mode.name.lowercase() + "_event_" + if (render.eventsAudible) "on" else "off"
                assertArrayEquals(N2QualificationExport.pcmBytes(render.pcm), File(output, "$prefix.pcm.f32le").readBytes())
                assertArrayEquals(N2QualificationExport.tapBytes(render.sourceTaps), File(output, "$prefix.taps.f64le").readBytes())
            }
            assertThrows(IllegalArgumentException::class.java) {
                N2QualificationExport.write(output, f, base, bytes)
            }
            assertEquals(hash, N2QualificationExport.sha(manifest.readBytes()))
        } finally { parent.deleteRecursively() }
    }

    @Test fun malformedArtifactDoesNotCreateOutputDirectory() {
        val parent = Files.createTempDirectory("n2-export-invalid").toFile()
        try {
            val output = File(parent, "never")
            assertThrows(IllegalArgumentException::class.java) {
                N2SyntheticReferenceExporter.export(output, baseline, byteArrayOf(1))
            }
            assertFalse(output.exists())
        } finally { parent.deleteRecursively() }
    }

    @Test fun hotLiftEventOnOffTrajectoriesPreserveOccurrenceAndLateTailAcrossPartitions() {
        val f = N2SyntheticReferenceExporter.fixture()
        val bytes = artifact; val base = baseline
        val block = N2QualificationExport.renderAll(f, base, bytes, intArrayOf(960))
        val split = N2QualificationExport.renderAll(f, base, bytes, intArrayOf(333, 297))
        block.zip(split).forEach { (a, b) ->
            assertArrayEquals(a.pcm, b.pcm, 0f)
            assertArrayEquals(N2QualificationExport.tapBytes(a.sourceTaps), N2QualificationExport.tapBytes(b.sourceTaps))
            assertArrayEquals(a.eventObservation.impulseFrames, b.eventObservation.impulseFrames)
            assertArrayEquals(a.eventObservation.arrivalFrames, b.eventObservation.arrivalFrames)
        }
        for (mode in listOf(N2Mode.E, N2Mode.SE)) {
            val on = block.single { it.mode == mode && it.eventsAudible }
            val off = block.single { it.mode == mode && !it.eventsAudible }
            assertTrue("fixture must actually excite events", on.eventObservation.distinctImpulseFrames > 0)
            assertArrayEquals(on.eventObservation.impulseFrames, off.eventObservation.impulseFrames)
            assertArrayEquals(on.eventObservation.arrivalAmplitudes, off.eventObservation.arrivalAmplitudes, 0.0)
            assertFalse(on.pcm.contentEquals(off.pcm))
            on.sourceTaps.indices.forEach { i ->
                for (channel in 0..8) if (channel != 4) {
                    assertEquals(on.sourceTaps[i][channel], off.sourceTaps[i][channel], 0.0)
                }
                assertEquals(0.0, off.sourceTaps[i][4], 0.0)
            }
            val lastImpulse = on.sourceTaps.indexOfLast { it[8] != 0.0 }
            assertTrue(lastImpulse >= 0 && lastImpulse + N2Profile.EVENT_LENGTH < f.frames)
            assertTrue("late event tail must not disappear", on.sourceTaps
                .slice(lastImpulse + 8192 until lastImpulse + N2Profile.EVENT_LENGTH).any { it[4] != 0.0 })
            assertTrue(on.sourceTaps.drop(lastImpulse + N2Profile.EVENT_LENGTH).all { it[4] == 0.0 })
        }
    }
}
