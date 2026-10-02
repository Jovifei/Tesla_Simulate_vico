package com.vico.simulator.sound

import com.vico.simulator.sound.s18.C63QualificationReport
import com.vico.simulator.sound.s18.QualificationGate
import org.junit.Assert.*
import org.junit.Test

class C63QualificationRouteTest {
    private val hash = "a".repeat(64)
    private val state = SoundState(0.0, 700.0, 0.0, .5, .5, floatArrayOf(), false, .5, .5)
    private inner class Provider(
        val id: String = "C63_TEST",
        val output: () -> FloatArray = { FloatArray(960) { .25f } },
    ) : C63QualificationPcmProvider {
        var report = C63QualificationReport(id, hash, hash, hash,
            QualificationGate.values().associateWith { true }, mapOf("finite" to true, "frames" to 960))
        override fun candidateId() = id
        override fun qualification() = report
        override fun profileHash() = hash
        override fun sourceHash() = hash
        override fun render(state: SoundState, frames: Int) = output()
    }

    @Test fun defaultAndUnqualifiedUseLegacyFallback() {
        val route = C63QualificationRoute()
        assertNull(route.render(state, 960, 48000))
        assertFalse(route.prepare(Provider("C63_HY1_SE")))
        val provider = Provider()
        provider.report = provider.report.copy(profileHash = "unknown")
        assertFalse(route.prepare(provider))
        assertNull(route.render(state, 960, 48000))
    }

    @Test fun candidateOutputIsDetachedAndClearedByLifecycle() {
        val buffer = FloatArray(960) { .25f }
        val route = C63QualificationRoute()
        assertTrue(route.prepare(Provider(output = { buffer })))
        val pcm = route.render(state, 960, 48000)!!
        buffer.fill(.5f)
        assertEquals(.25f, pcm[0], 0f)
        route.clear()
        assertNull(route.render(state, 960, 48000))
    }

    @Test fun invalidPcmOrExceptionClearsCandidate() {
        for (output in listOf<() -> FloatArray>(
            { FloatArray(1) }, { FloatArray(960) { Float.NaN } },
            { FloatArray(960) { 1.1f } }, { error("renderer failed") },
        )) {
            val route = C63QualificationRoute()
            assertTrue(route.prepare(Provider(output = output)))
            assertNull(route.render(state, 960, 48000))
            assertNull(route.render(state, 960, 48000))
        }
    }

    @Test fun qualificationRevocationAndInvalidInputUseFallback() {
        val route = C63QualificationRoute()
        val provider = Provider()
        assertTrue(route.prepare(provider))
        provider.report = provider.report.copy(gates = emptyMap())
        assertNull(route.render(state, 960, 48000))
        assertTrue(route.prepare(Provider()))
        assertNull(route.render(state.copy(rpm = Double.NaN), 960, 48000))
        assertTrue(route.prepare(Provider()))
        assertNull(route.render(state, 960, 44100))
    }

    @Test fun preparingRejectedCandidateClearsPreviousSelection() {
        val route = C63QualificationRoute()
        assertTrue(route.prepare(Provider()))
        assertFalse(route.prepare(Provider("C63_HY1")))
        assertNull(route.render(state, 960, 48000))
    }
}
