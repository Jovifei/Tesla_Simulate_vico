package com.vico.simulator.sound

import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class C63QualificationSelectorTest {
    private class Provider(private val id: String) : C63QualificationPcmProvider {
        override fun render(state: SoundState, frames: Int) = FloatArray(frames)
        override fun candidateId() = id
    }

    @Test
    fun rejectsMissingQualification() {
        assertNull(C63QualificationSelector().select(Provider("CANDIDATE"), "CANDIDATE", false, true))
    }

    @Test
    fun rejectsFrozenHy1DerivedIdentity() {
        assertNull(C63QualificationSelector().select(Provider("C63_HY1_SE"), "C63_HY1_SE", true, true))
    }

    @Test
    fun acceptsValidatedNonFrozenProvider() {
        assertNotNull(C63QualificationSelector().select(Provider("C63_CANDIDATE_V2"), "C63_CANDIDATE_V2", true, true))
    }
}
