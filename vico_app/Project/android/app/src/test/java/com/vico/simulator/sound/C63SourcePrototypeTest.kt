package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63SourcePrototype
import org.junit.Assert.*
import org.junit.Test

class C63SourcePrototypeTest {
    @Test fun restored_state_preserves_filter_noise_and_event_tail() {
        val original=C63SourcePrototype()
        repeat(48000){original.sample(5000.0,.9,.9)}
        repeat(1000){original.sample(5000.0,.05,.05)}
        val saved=original.snapshot();val restored=C63SourcePrototype();restored.restore(saved)
        repeat(48000){assertEquals(original.sample(4500.0,.1,.05),restored.sample(4500.0,.1,.05),0f)}
    }
    @Test fun export_opt_in_original_trace_candidate() {
        val destination=System.getenv("VICO_S15_PCM")
        org.junit.Assume.assumeTrue(!destination.isNullOrBlank())
        val path=java.nio.file.Paths.get(requireNotNull(destination))
        assertFalse(java.nio.file.Files.exists(path))
        val trace=java.io.File("src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json").readText()
        fun field(name:String)=Regex("\"$name\"\\s*:\\s*([-+0-9.eE]+)").findAll(trace).map{it.groupValues[1].toDouble()}.toList()
        val times=field("time_s");val rpm=field("rpm");val loads=field("load");val throttle=field("throttle")
        assertEquals(times.size,rpm.size);assertEquals(times.size,loads.size);assertEquals(times.size,throttle.size)
        val engine=C63SourcePrototype();var cursor=0
        val bytes=java.nio.ByteBuffer.allocate(1440000*4).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        for(n in 0 until 1440000) {
            val t=n/48000.0
            while(cursor+1<times.size-1 && times[cursor+1]<=t)cursor++
            val f=((t-times[cursor])/(times[cursor+1]-times[cursor])).coerceIn(0.0,1.0)
            fun interpolate(values:List<Double>)=values[cursor]+f*(values[cursor+1]-values[cursor])
            val value=engine.sample(interpolate(rpm),interpolate(loads),interpolate(throttle))
            assertTrue(value.isFinite());assertTrue(kotlin.math.abs(value)<1f)
            bytes.putFloat(value)
        }
        java.nio.file.Files.write(path,bytes.array())
    }
    private fun render(block: Int,finite:Boolean=false): FloatArray {
        val engine=C63SourcePrototype(finite);val output=FloatArray(48000);var first=0
        while(first<output.size) {
            for(n in first until minOf(first+block,output.size)) output[n]=engine.sample(4000.0,.7,if(n<24000) .7 else .05)
            first+=block
        }
        return output
    }
    @Test fun partition_does_not_reset_state() {
        val golden=render(96)
        for(block in listOf(192,240,256,480,960)) assertArrayEquals(golden,render(block),0f)
    }
    @Test fun finite_pressure_partition_and_mid_queue_restore_are_exact() {
        val golden=render(96,true)
        for(block in listOf(192,240,256,480,960))assertArrayEquals(golden,render(block,true),0f)
        val a=C63SourcePrototype(true);repeat(7){a.sample(4100.0,.4,.4)}
        val b=C63SourcePrototype(true);b.restore(a.snapshot())
        repeat(48000){assertEquals(a.sample(4100.0,.4,.4),b.sample(4100.0,.4,.4),0f)}
    }
    @Test fun finite_nonzero_source() {
        val x=render(256)
        assertTrue(x.all{it.isFinite()});assertTrue(x.any{kotlin.math.abs(it)>.0001f});assertTrue(x.all{kotlin.math.abs(it)<1f})
    }
    @Test(expected=IllegalArgumentException::class) fun invalid_input_is_rejected() {
        C63SourcePrototype().sample(Double.NaN,.5,.5)
    }
    @Test fun hot_tip_out_generates_events_without_clip_and_cold_closed_does_not() {
        val hot=C63SourcePrototype();val cold=C63SourcePrototype()
        repeat(48000){hot.sample(5000.0,.9,.9);cold.sample(5000.0,.05,.05)}
        repeat(48000){hot.sample(5000.0,.05,.05);cold.sample(5000.0,.05,.05)}
        assertTrue(hot.afterfireEvents>0);assertEquals(0L,cold.afterfireEvents)
    }
    @Test fun identical_prefix_cannot_depend_on_future() {
        val a=C63SourcePrototype();val b=C63SourcePrototype()
        repeat(48000){ assertEquals(a.sample(3500.0,.6,.6),b.sample(3500.0,.6,.6),0f) }
        repeat(1000){a.sample(2000.0,.1,.1);b.sample(6000.0,.9,.9)}
    }
}
