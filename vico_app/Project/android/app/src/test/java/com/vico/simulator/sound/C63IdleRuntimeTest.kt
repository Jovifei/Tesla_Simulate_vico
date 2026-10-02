package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63IdleRuntime
import org.junit.Assert.*
import org.junit.Test
class C63IdleRuntimeTest {
    @Test fun full_throttle_low_rpm_is_not_an_idle_state() {
        val idle=C63IdleRuntime()
        repeat(48000){assertEquals(0.0,idle.sample(1700.0,1.0,1.0),0.0)}
    }
    @Test fun idle_produces_finite_pressure() {
        val idle=C63IdleRuntime();val x=DoubleArray(48000){idle.sample(750.0,.3)}
        assertTrue(x.all{it.isFinite()});assertTrue(x.any{kotlin.math.abs(it)>1e-6})
    }
    @Test fun no_new_idle_excitation_at_high_rpm() {
        val idle=C63IdleRuntime()
        repeat(48000){assertEquals(0.0,idle.sample(3000.0,.7),0.0)}
    }
}
