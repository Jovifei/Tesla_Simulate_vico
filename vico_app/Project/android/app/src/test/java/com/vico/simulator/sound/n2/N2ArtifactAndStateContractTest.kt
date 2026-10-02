package com.vico.simulator.sound.n2

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class N2ArtifactAndStateContractTest {
    @Test
    fun binaryArtifactRoundTripsFrozenCalibrationIdentity() {
        val profile = N2Profile.preregistered()
        val artifact = N2ProfileArtifactLoader.export(profile)
        val loaded = N2ProfileArtifactLoader.verify(artifact.bytes, profile.identity)
        assertEquals(profile.identity, loaded.identity)
        assertEquals(13.728409855272066, loaded.sourceScale, 0.0)
        assertTrue(loaded.artifactHash.length == 64)
    }

    @Test
    fun transactionalRestoreDoesNotApplyAfterValidationFailure() {
        var value = 3
        try {
            N2TransactionalRestore.restoreAtomically({
                throw IllegalArgumentException("bad child snapshot")
            }, { value = 9 })
        } catch (_: IllegalArgumentException) {
        }
        assertEquals(3, value)
    }
}
