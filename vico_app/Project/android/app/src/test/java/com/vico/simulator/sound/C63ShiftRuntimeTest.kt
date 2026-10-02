package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63ShiftRuntime
import org.junit.Assert.*
import org.junit.Test
class C63ShiftRuntimeTest {
    @Test fun steady_input_is_unchanged_without_event() {
        val shift=C63ShiftRuntime();repeat(1000){assertEquals(.2,shift.sample(.2,false),0.0)}
    }
    @Test fun event_has_interruption_and_recovery_without_wav() {
        val shift=C63ShiftRuntime()
        val x=DoubleArray(24000){shift.sample(.2,it==0)}
        assertTrue(x.all{it.isFinite()});assertTrue(x.take(4800).any{it<.15})
        assertEquals(.2,x.last(),1e-6)
    }
}
