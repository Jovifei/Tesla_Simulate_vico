package com.vico.simulator.sound

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.abs
import kotlin.math.PI
import kotlin.math.sin
import kotlin.math.exp
import java.util.concurrent.CountDownLatch

class NormalLoopTraversalTest {
    private fun normal(bank: MatlabSoundBank): MatlabStatefulBankRenderer {
        val mode = LoopTraversalMode.values().firstOrNull { it.name == "NORMAL_CANONICAL_SEAM_V1" }
            ?: LoopTraversalMode.LEGACY_LOCKED
        return MatlabStatefulBankRenderer(bank, mode)
    }

    @Test fun both_wrapping_interpolation_junctions_have_matching_left_and_right_slopes() {
        val bank = bank(); val loop = bank.loops.single()
        val original = MatlabStatefulBankRenderer(bank); val softened = normal(bank)
        val step = .002
        for (junction in listOf(0.0, loop.samples.lastIndex.toDouble())) {
            fun gap(renderer: MatlabStatefulBankRenderer): Double {
                val left = sourceSample(renderer, loop, junction - step)
                val middle = sourceSample(renderer, loop, junction)
                val right = sourceSample(renderer, loop, junction + step)
                return abs((middle - left) / step - (right - middle) / step)
            }
            assertTrue("fixture must expose junction $junction", gap(original) > .15)
            assertTrue("both source seam slopes must agree at junction $junction", gap(softened) < .002)
        }
    }

    @Test fun source_support_exterior_and_endpoints_retain_exact_legacy_float_bits() {
        val base = bank(); val loop = base.loops.single()
        val old = MatlabStatefulBankRenderer(base); val corrected = normal(base)
        var point = 8.0
        while (point <= loop.samples.lastIndex - 8.0) {
            val a = sourceSample(old, loop, point).toFloat()
            val b = sourceSample(corrected, loop, point).toFloat()
            assertEquals("unchanged source coordinate $point", a.toRawBits(), b.toRawBits())
            point += .125
        }
        assertEquals(0L, corrected.traversalStats()!!.correctedReads)
    }

    @Test fun support_edges_join_with_zero_added_slope() {
        val base = bank(); val loop = base.loops.single()
        val old = MatlabStatefulBankRenderer(base); val corrected = normal(base)
        val h = .002
        for (edge in listOf(8.0, loop.samples.lastIndex - 8.0)) {
            val legacySlope = (sourceSample(old, loop, edge + h) - sourceSample(old, loop, edge - h)) / (2 * h)
            val left = (sourceSample(corrected, loop, edge) - sourceSample(corrected, loop, edge - h)) / h
            val right = (sourceSample(corrected, loop, edge + h) - sourceSample(corrected, loop, edge)) / h
            assertEquals(legacySlope, left, .001)
            assertEquals(legacySlope, right, .001)
        }
    }

    @Test fun constant_source_keeps_gain_and_pcm_exact_through_seams() {
        val renderer = normal(bank(constant = true))
        assertTrue(renderer.render(state(), 20_000).all { it == .3f })
        assertEquals(0.0, renderer.traversalStats()!!.maxAbsCorrection, 0.0)
        assertEquals(0L, renderer.traversalStats()!!.correctedReads)
    }

    @Test fun correction_does_not_hide_a_synthetic_peak_contract_counterexample() {
        val base = bank().let { b -> b.copy(loops = b.loops.map { it.copy(samples = FloatArray(128) { index -> if (index < 2) -.8f else .8f }) }) }
        val old = MatlabStatefulBankRenderer(base); val corrected = normal(base)
        old.render(state(), 1000); val output = corrected.render(state(), 1000)
        assertEquals(0L, old.mixStats().aboveContractFrames)
        assertTrue("actual source veto must remain visible", corrected.mixStats().aboveContractFrames > 0)
        assertTrue(corrected.mixStats().preClipPeak > 1.0)
        assertTrue(corrected.mixStats().hardClipFrames > 0)
        assertTrue(output.all { abs(it) <= 1.0 })
    }

    @Test fun normal_sample_peak_and_nonfinite_statistics_remain_valid() {
        val renderer = normal(bank())
        renderer.render(state(), 30_000)
        assertTrue(renderer.mixStats().preClipPeak < .8413951416451951)
        assertEquals(0L, renderer.mixStats().aboveContractFrames)
        assertEquals(0L, renderer.mixStats().hardClipFrames)
        assertEquals(0L, renderer.mixStats().nonFiniteFrames)
        assertTrue(renderer.traversalStats()!!.correctedReads > 0)
    }

    @Test fun short_loops_below_twenty_percent_support_limit_retain_legacy_bits() {
        val base = bank(count = 84); val corrected = normal(base)
        assertArrayEquals(MatlabStatefulBankRenderer(base).render(state(), 3000), corrected.render(state(), 3000), 0f)
        assertEquals(0L, corrected.traversalStats()!!.correctedReads)
        assertTrue(corrected.traversalStats()!!.skippedShortLoopReads > 0)
    }

    @Test fun partitions_and_arbitrary_ui_time_stamps_preserve_dynamic_pcm_bits() {
        val base = layers()
        fun render(partition: Int): FloatArray {
            val renderer = normal(base); val out = FloatArray(96_000)
            for (block in 0 until 100) {
                val rpm = when (block / 20 % 3) { 0 -> 910.0; 1 -> 6231.0; else -> 3000.0 }
                val load = if (block % 7 < 3) .3 else .9
                var within = 0
                while (within < 960) {
                    val count = minOf(partition, 960 - within)
                    renderer.render(state(rpm).copy(load = load, timeS = block * 97.0 + within), count).copyInto(out, block * 960 + within)
                    within += count
                }
            }
            return out
        }
        val reference = render(960)
        for (size in listOf(1, 333, 997)) assertArrayEquals("frame partition $size", reference, render(size), 0f)
    }

    @Test fun inactive_layer_reads_and_reactivation_do_not_change_canonical_phase_or_output() {
        val base = layers(); val first = NormalLoopTraversal(base, "same-bank"); val reference = NormalLoopTraversal(base, "same-bank")
        var cycles = 0.0
        repeat(20_000) { frame ->
            val active = if (frame in 4000..7999) base.loops[4] else base.loops[0]
            for (inactive in base.loops) if (inactive !== active) first.sample(inactive, cycles)
            assertEquals(reference.sample(active, cycles).toRawBits(), first.sample(active, cycles).toRawBits())
            cycles += 4300.0 / 120 / 48_000
        }
    }

    @Test fun all_256_control_edges_and_maximum_smoothing_ramps_keep_canonical_coordinates() {
        val base = layers(); val alpha = 1 - exp(-1.0 / 48_000 / .035)
        for (bucket in 0 until 256) for (side in listOf(-1.0, 1.0)) {
            val correction = NormalLoopTraversal(base, "fixed-bank")
            var cycles = 0.0
            var rpm = (6231.0 * (bucket + 1) / 256 + side * 1e-8).coerceIn(910.0, 6231.0)
            repeat(1000) {
                for (loop in base.loops) {
                    val value = correction.sample(loop, cycles)
                    assertTrue(value.isFinite())
                    val span = loop.samples.size.toDouble() / 48_000 * loop.rpm / 120
                    val point = cycles % span / span * loop.samples.size
                    if (point >= 8 && point <= loop.samples.lastIndex - 8) {
                        val at = kotlin.math.floor(point).toInt()
                        val fraction = (point - at).toFloat()
                        val expected = loop.samples[at] + (loop.samples[(at + 1) % loop.samples.size] - loop.samples[at]) * fraction
                        assertEquals(expected.toRawBits(), value.toRawBits())
                    }
                }
                cycles += rpm / 120 / 48_000
                rpm += alpha * (6231.0 - rpm)
            }
        }
    }

    @Test fun events_remain_independent_and_same_timestamp_triggers_are_not_replayed() {
        val base = bank(constant = true).let { b -> b.copy(loops = b.loops.map { it.copy(samples = FloatArray(128)) },
            afterfire = floatArrayOf(.3f, -.2f, .1f), shiftEvents = listOf(MatlabTransient("shift", floatArrayOf(.4f, .2f, .05f)))) }
        val old = MatlabStatefulBankRenderer(base); val corrected = normal(base)
        val trigger = state().copy(timeS = 10.0, afterfireTrigger = true, shiftTrigger = true)
        assertArrayEquals(old.render(trigger, 3000), corrected.render(trigger, 3000), 0f)
        assertArrayEquals(old.render(trigger, 3000), corrected.render(trigger, 3000), 0f)
        old.clearTransientEvents(); corrected.clearTransientEvents()
        assertArrayEquals(old.render(trigger.copy(timeS = 11.0), 3000), corrected.render(trigger.copy(timeS = 11.0), 3000), 0f)
    }

    @Test fun clearing_events_preserves_phase_and_proper_reset_restarts_canonical_sequence() {
        val a = normal(bank()); val b = normal(bank())
        assertArrayEquals(a.render(state(), 18_731), b.render(state(), 18_731), 0f)
        b.clearTransientEvents()
        assertArrayEquals(a.render(state(), 20_000), b.render(state(), 20_000), 0f)
        b.reset()
        assertEquals(0L, b.traversalStats()!!.correctedReads)
        assertArrayEquals(normal(bank()).render(state(), 5000), b.render(state(), 5000), 0f)
    }

    @Test fun prepared_source_reads_do_not_allocate_per_audio_frame() {
        val base = bank(); val correction = NormalLoopTraversal(base, "allocation-fixture"); val loop = base.loops.single()
        val meter = Class.forName("java.lang.management.ManagementFactory").getMethod("getThreadMXBean").invoke(null)
        val api = Class.forName("com.sun.management.ThreadMXBean")
        api.getMethod("setThreadAllocatedMemoryEnabled", Boolean::class.javaPrimitiveType).invoke(meter, true)
        val readBytes = api.getMethod("getThreadAllocatedBytes", Long::class.javaPrimitiveType)
        val threadId = Thread.currentThread().id
        var cycles = 0.0; var sum = 0.0
        repeat(30_000) { sum += correction.sample(loop, cycles); cycles += 6231.0 / 120 / 48_000 }
        val before = readBytes.invoke(meter, threadId) as Long
        repeat(20_000) { sum += correction.sample(loop, cycles); cycles += 6231.0 / 120 / 48_000 }
        val allocated = (readBytes.invoke(meter, threadId) as Long) - before
        assertTrue(sum.isFinite())
        assertTrue("prepared source path allocated $allocated bytes/20000 frames", allocated <= 1024)
    }

    @Test fun busy_owner_blocks_preparation_and_idle_owner_resets_only_normal() {
        // Android shells are unused; actual AudioEngine gate and initialized model methods execute.
        val unsafeType = Class.forName("sun.misc.Unsafe")
        val unsafe = unsafeType.getDeclaredField("theUnsafe").apply { isAccessible = true }.get(null)
        val allocate = unsafeType.getMethod("allocateInstance", Class::class.java)
        val assets = allocate.invoke(unsafe, android.content.res.AssetManager::class.java) as android.content.res.AssetManager
        val model = MatlabV6SoundBankEngine(assets)
        val rendererField = MatlabV6SoundBankEngine::class.java.getDeclaredField("renderer").apply { isAccessible = true }
        val engine = allocate.invoke(unsafe, AudioEngine::class.java) as AudioEngine
        AudioEngine::class.java.getDeclaredField("model").apply { isAccessible = true }.set(engine, model)
        val running = AudioEngine::class.java.getDeclaredField("running").apply { isAccessible = true }
        val thread = AudioEngine::class.java.getDeclaredField("thread").apply { isAccessible = true }
        val renderer = normal(bank()); val reference = normal(bank())
        rendererField.set(model, renderer)
        renderer.render(state(), 1000); reference.render(state(), 1000)
        running.setBoolean(engine, true); assertFalse(engine.prepareControllerSession())
        assertArrayEquals(reference.render(state(), 1000), renderer.render(state(), 1000), 0f)
        running.setBoolean(engine, false)
        val started = CountDownLatch(1); val release = CountDownLatch(1)
        val writer = Thread { started.countDown(); release.await() }
        writer.start(); started.await(); thread.set(engine, writer)
        try { assertFalse(engine.prepareControllerSession()) }
        finally { release.countDown(); writer.join(1000); thread.set(engine, null) }
        assertTrue(engine.prepareControllerSession())
        assertArrayEquals(normal(bank()).render(state(), 3000), renderer.render(state(), 3000), 0f)
        val old = MatlabStatefulBankRenderer(bank()); val oldReference = MatlabStatefulBankRenderer(bank())
        rendererField.set(model, old)
        old.render(state(), 1000); oldReference.render(state(), 1000)
        assertTrue(engine.prepareControllerSession())
        assertArrayEquals(oldReference.render(state(), 1000), old.render(state(), 1000), 0f)
    }

    private fun layers(): MatlabSoundBank = bank().copy(loops = listOf(910.0, 3000.0, 6231.0).flatMap { rpm ->
        listOf(.3, .9).map { load -> MatlabLoop(rpm, load, FloatArray(128) { i -> (.15 * sin(i * .083) + .05 * sin(i * .021)).toFloat() }) }
    })

    private fun sourceSample(renderer: MatlabStatefulBankRenderer, loop: MatlabLoop, position: Double): Double {
        val size = loop.samples.size
        val canonical = ((position % size) + size) % size
        val cycles = size.toDouble() / 48_000 * loop.rpm / 120.0
        MatlabStatefulBankRenderer::class.java.getDeclaredField("engineCycles").apply { isAccessible = true }
            .setDouble(renderer, canonical / size * cycles)
        return renderer.render(state(loop.rpm), 1).single().toDouble()
    }

    private fun state(rpm: Double = 6231.0) = SoundState(0.0, rpm, 1.0, 1.0, 1.0, floatArrayOf(), false, load = .3, shiftGain = 1.0)

    private fun bank(count: Int = 128, constant: Boolean = false): MatlabSoundBank {
        val samples = FloatArray(count) { if (constant) .3f else (-.15 + .55 * it / (count - 1)).toFloat() }
        return MatlabSoundBank("two-junction-fixture", 48_000, MatlabPowertrainSpec(
            6231.0, 6231.0, doubleArrayOf(3.0, 2.0), 3.0, .3, 6231.0, 6231.0,
            .018, .032, .075, .055, .22, 1.08, .35, .68, 144.0,
        ), listOf(MatlabLoop(6231.0, .3, samples)), floatArrayOf())
    }
}
