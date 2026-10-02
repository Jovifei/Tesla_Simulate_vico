package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63RuntimeRenderer
import org.junit.Assert.*
import org.junit.Test
class C63RuntimeRendererTest {
    @Test fun snapshot_restores_entire_idle_shift_output_and_source_chain() {
        val a=C63RuntimeRenderer()
        repeat(30){a.render(state(it*.02,700.0).copy(load=.14,throttle=.14),960)}
        repeat(100){a.render(state(.6+it*.02,4000.0).copy(load=.4,throttle=.4),960)}
        a.render(state(2.6,4000.0).copy(load=.05,throttle=.05,shiftTrigger=true),960)
        val saved=a.snapshot();val b=C63RuntimeRenderer();b.restore(saved)
        repeat(50){n->
            val s=state(2.62+n*.02,4000.0).copy(load=.05,throttle=.05)
            assertArrayEquals(a.render(s,960),b.render(s,960),0f)
        }
    }
    @Test fun recorded_phone_startup_input_must_not_violate_peak_gate() {
        val text=java.io.File("E:\\Tesla_speed\\review_packages\\s15-20261001\\device-smoke-performance-fix.json").readText()
        val rows=Regex("\\[\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*\\]").findAll(text).map{m->(1..6).map{m.groupValues[it].toDouble()}}.toList()
        assertTrue(rows.size>=38)
        val runtime=C63RuntimeRenderer(finiteExcitation=true)
        for(row in rows)runtime.render(state(row[0],row[1]).copy(load=row[2],throttle=row[3],shiftTrigger=row[4]!=0.0),row[5].toInt())
        assertTrue(runtime.peak<=.8413951416451951)
    }
    @Test fun production_anchor_grid_stays_inside_candidate_peak_contract() {
        for(rpm in listOf(700.0,1400.0,2200.0,3200.0,4300.0,5500.0,6800.0,7200.0)) {
            for(load in listOf(.0,.32,.92,1.0)) {
                val runtime=C63RuntimeRenderer(finiteExcitation=true)
                repeat(50){runtime.render(state(it*.02,rpm).copy(load=load,throttle=load),960)}
                assertTrue("rpm=$rpm load=$load peak=${runtime.peak}",runtime.peak<=.8413951416451951)
            }
        }
    }
    @Test fun original_trace_complete_pipeline_opt_in() {
        val destination=System.getenv("VICO_S15_RUNTIME_OUTPUT")
        org.junit.Assume.assumeTrue(!destination.isNullOrBlank())
        val text=java.io.File("src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json").readText()
        fun field(name:String)=Regex("\"$name\"\\s*:\\s*([-+0-9.eE]+)").findAll(text).map{it.groupValues[1].toDouble()}.toList()
        val times=field("time_s");val rpms=field("rpm");val loads=field("load");val throttles=field("throttle")
        val pipeline=C63RuntimeRenderer()
        val bytes=java.nio.ByteBuffer.allocate(1440000*4).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        val shiftTimes=doubleArrayOf(6.100416666666667,8.620291666666667,11.1424375)
        var event=0
        for(block in 0 until 1500) {
            val t=block*.02
            val shifted=event<shiftTimes.size && t>=shiftTimes[event]
            if(shifted)event++
            val s=state(t,rpms[block]).copy(load=loads[block],throttle=throttles[block],shiftTrigger=shifted)
            pipeline.render(s,960).forEach{bytes.putFloat(it)}
        }
        assertEquals(1440000L,pipeline.frames)
        val path=java.nio.file.Paths.get(requireNotNull(destination));assertFalse(java.nio.file.Files.exists(path))
        java.nio.file.Files.write(path,bytes.array())
    }
    private fun state(time:Double,rpm:Double)=SoundState(time,rpm,rpm/60*4,.5,.5,floatArrayOf(),false,.5,.5)
    @Test fun completed_chain_is_finite_and_bounded_on_basic_input() {
        val runtime=C63RuntimeRenderer()
        repeat(50){assertTrue(runtime.render(state(it*.02,2000.0),960).all{it.isFinite()})}
        assertEquals(48000L,runtime.frames);assertTrue(runtime.peak<=.8413951416451951)
    }
}
