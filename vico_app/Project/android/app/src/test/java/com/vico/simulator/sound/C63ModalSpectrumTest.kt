package com.vico.simulator.sound
import com.vico.simulator.sound.s17.C63ModalSpectrum
import kotlin.math.PI
import kotlin.math.sin
import org.junit.Assert.*
import org.junit.Test
class C63ModalSpectrumTest {
    @Test fun linePowerIsFiniteNonnegativeAndCoherent() {
        val samples=FloatArray(48000){(.5*sin(2*PI*1000*it/48000)).toFloat()}
        assertTrue(C63ModalSpectrum.linePower(samples,1000.0)>0.05)
        assertTrue(C63ModalSpectrum.linePower(samples,960.0)>=0.0)
        assertTrue(C63ModalSpectrum.prominence(samples,1000.0).isFinite())
    }
    @Test fun invalidFrequencyIsRejected() {
        assertThrows(IllegalArgumentException::class.java){C63ModalSpectrum.linePower(FloatArray(16),Double.NaN)}
    }
}
