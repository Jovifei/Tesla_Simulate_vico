package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

class NormalEnvelopeIntegrationTest {
    private fun normal(bank: MatlabSoundBank) = MatlabStatefulBankRenderer(bank,
        LoopTraversalMode.values().firstOrNull { it.name == "NORMAL_SEAM_ENVELOPE_V1" }
            ?: LoopTraversalMode.NORMAL_CANONICAL_SEAM_V1)

    @Test fun actual_normal_mix_reduces_slow_modulation_without_repositioning_source() {
        val bank = bank()
        val baseline = MatlabStatefulBankRenderer(bank, LoopTraversalMode.NORMAL_CANONICAL_SEAM_V1)
        val actual = normal(bank)
        val a = baseline.render(state(), 288000)
        val b = actual.render(state(), 288000)
        for (i in 0 until 12000) assertEquals(a[i].toRawBits(), b[i].toRawBits())
        assertTrue("normal slow modulation must decrease, not remain a passthrough",
            modulationPower(b) / modulationPower(a) < .75)
        for (i in a.indices) {
            assertTrue("bounded effective amplitude at $i", kotlin.math.abs(b[i] - a[i]) <= kotlin.math.abs(a[i]) * .03001 + 1e-8)
        }
    }

    @Test fun independent_events_do_not_enter_the_envelope_tracker() {
        val bank = bank().copy(afterfire = FloatArray(100) { .025f })
        val dry = normal(bank); val withEvent = normal(bank)
        assertArrayEquals(dry.render(state(), 24000), withEvent.render(state(), 24000), 0f)
        val a = dry.render(state().copy(timeS = .5), 2000)
        val b = withEvent.render(state().copy(timeS = .5, afterfireTrigger = true), 2000)
        for (i in a.indices) {
            val expected = if (i < 100) a[i] + .025f else a[i]
            assertEquals("event is added after shaping at $i", expected.toRawBits(), b[i].toRawBits())
        }
        assertArrayEquals(dry.render(state(), 5000), withEvent.render(state(), 5000), 0f)
    }

    @Test fun transient_clear_preserves_continuous_envelope_and_phase() {
        val bank = bank(); val a = normal(bank); val b = normal(bank)
        a.render(state(), 30000); b.render(state(), 30000)
        a.clearTransientEvents()
        assertArrayEquals(b.render(state(), 30000), a.render(state(), 30000), 0f)
    }

    @Test fun renderer_reset_restarts_the_same_envelope_and_phase() {
        val bank = bank(); val actual = normal(bank)
        actual.render(state(), 70000); actual.reset()
        assertArrayEquals(normal(bank).render(state(), 70000), actual.render(state(), 70000), 0f)
    }

    @Test fun actual_render_partitions_have_identical_float_bits() {
        val bank = bank(); val expected = normal(bank).render(state(), 70000)
        for (block in listOf(1,333,960,997)) {
            val renderer = normal(bank); val actual = FloatArray(expected.size)
            var first = 0
            while (first < actual.size) {
                val count = minOf(block, actual.size-first)
                renderer.render(state(), count).copyInto(actual,first); first += count
            }
            assertArrayEquals("partition $block", expected, actual, 0f)
        }
    }

    @Test fun idle_model_preparation_resets_the_new_normal_mode() {
        val unsafeType = Class.forName("sun.misc.Unsafe")
        val unsafe = unsafeType.getDeclaredField("theUnsafe").apply { isAccessible=true }.get(null)
        val assets = unsafeType.getMethod("allocateInstance",Class::class.java)
            .invoke(unsafe,android.content.res.AssetManager::class.java) as android.content.res.AssetManager
        val model = MatlabV6SoundBankEngine(assets); val renderer = normal(bank())
        MatlabV6SoundBankEngine::class.java.getDeclaredField("renderer").apply { isAccessible=true }.set(model,renderer)
        renderer.render(state(),70000)
        assertTrue(model.prepareControllerSession())
        assertArrayEquals(normal(bank()).render(state(),70000),renderer.render(state(),70000),0f)
    }

    private fun modulationPower(x: FloatArray): Double {
        var real=0.0;var imaginary=0.0;var count=0
        var total=0.0;var cosTotal=0.0;var sinTotal=0.0
        for (first in 96000 until x.size-480 step 480) {
            var energy=0.0
            for (i in first until first+480) energy+=x[i].toDouble()*x[i]
            val envelope=sqrt(energy/480)
            val angle=2*PI*1.8055555555555556*(first+240)/48000
            real+=envelope*cos(angle);imaginary-=envelope*sin(angle);count++
            total+=envelope;cosTotal+=cos(angle);sinTotal+=sin(angle)
        }
        real-=total/count*cosTotal;imaginary+=total/count*sinTotal
        return (real*real+imaginary*imaginary)/(count*count)
    }

    private fun state() = SoundState(0.0,910.0,1.0,1.0,1.0,floatArrayOf(),false,load=.3,shiftGain=1.0)
    private fun bank(): MatlabSoundBank = MatlabSoundBank("normal-envelope-fixture",48000,MatlabPowertrainSpec(
        910.0,910.0,doubleArrayOf(3.0,2.0),3.0,.3,910.0,910.0,.018,.032,.075,.055,.22,1.08,.35,.68,144.0),
        listOf(MatlabLoop(910.0,.3,FloatArray(288000) { i ->
            val time=i/48000.0
            (.1*(1+.18*sin(2*PI*1.8055555555555556*time))*sin(2*PI*700*time)).toFloat()
        })),floatArrayOf())
}
