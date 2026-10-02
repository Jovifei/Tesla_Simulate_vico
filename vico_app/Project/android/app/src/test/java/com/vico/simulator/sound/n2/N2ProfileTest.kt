package com.vico.simulator.sound.n2

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class N2ProfileTest {
    @Test
    fun preregisteredProfileContainsEightRealFiniteResponses() {
        val profile = N2Profile.preregistered()
        assertEquals("C63_N2_CONTINUOUS_V1", N2Profile.CANDIDATE_ID)
        assertEquals(9, N2Profile.bandEdgesHz().size)
        repeat(N2Profile.BASIS_COUNT) { index ->
            val response = profile.basis(index)
            assertEquals(4096, response.size)
            assertTrue(abs(response.sum()) < 1e-8)
            assertEquals(1.0, response.sumOf { it * it }, 1e-6)
            assertTrue(response.any { it != 0.0 })
        }
        val event = profile.eventResponse()
        assertEquals(12288, event.size)
        assertTrue(event.copyOfRange(8192, event.size).sumOf { it * it } > 1e-8)
    }

    @Test
    fun returnedArraysCannotMutateBoundProfileIdentity() {
        val profile = N2Profile.preregistered()
        val identity = profile.identity
        profile.basis(0).fill(0.0)
        profile.coefficients().fill(0.0)
        profile.eventResponse().fill(0.0)
        assertEquals(identity, profile.identity)
        assertTrue(profile.basis(0).any { it != 0.0 })
    }

    @Test
    fun identityChangesWhenARegisteredCoefficientChanges() {
        val original = N2Profile.preregistered()
        val bank = Array(N2Profile.BASIS_COUNT) { original.basis(it) }
        val changed = original.coefficients().also { it[0] += .01 }
        val other = N2Profile(
            bank,
            changed,
            original.eventResponse(),
            original.eventNoiseA(),
            original.eventNoiseB(),
            sourceScale = original.sourceScale,
            randomFraction = original.randomFraction,
            eventScale = original.eventScale,
            eventNoiseFraction = original.eventNoiseFraction,
            sourceSeed = original.sourceSeed,
            occurrenceSeed = original.occurrenceSeed,
            responseSeed = original.responseSeed,
        )
        assertNotEquals(original.identity, other.identity)
    }
}
