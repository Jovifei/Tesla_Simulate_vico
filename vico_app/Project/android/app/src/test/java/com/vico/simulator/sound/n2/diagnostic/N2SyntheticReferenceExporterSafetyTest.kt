package com.vico.simulator.sound.n2.diagnostic

import org.junit.Assert.assertThrows
import org.junit.Test
import java.nio.file.Files

/**
 * Safety contract for diagnostic exporters: existing destinations are rejected.
 * The opt-in exporter must never delete or overwrite prior generated diagnostics.
 */
class N2SyntheticReferenceExporterSafetyTest {
    @Test
    fun existingDiagnosticFolderIsRejected() {
        val folder = Files.createTempDirectory("n2-export-existing").toFile()
        assertThrows(IllegalArgumentException::class.java) {
            N2SyntheticReferenceExporter.export(folder)
        }
    }
}
