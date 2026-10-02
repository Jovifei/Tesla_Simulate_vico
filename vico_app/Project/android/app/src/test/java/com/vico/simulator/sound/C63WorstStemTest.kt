package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63SourcePrototype
import com.vico.simulator.sound.s15.FrozenC63Output
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

class C63WorstStemTest {
    @Test fun worst_Q2_mode_is_measured_offline_by_unchanged_output_per_stem() {
        val dest=System.getenv("VICO_S15_TRI14_OUTPUT");Assume.assumeTrue(!dest.isNullOrBlank())
        val root=File(requireNotNull(dest));val names=listOf("exhaust","bark","intake","mechanical","afterfire","body","rumble")
        for(finite in listOf(false,true)) {
            val source=C63SourcePrototype(finite);val pipelines=Array(7){FrozenC63Output()}
            val data=Array(7){ByteBuffer.allocate(144000*4).order(ByteOrder.LITTLE_ENDIAN)}
            repeat(144000){source.sample(4100.0,1.0,1.0);for(i in 0 until 7)data[i].putFloat(pipelines[i].sample(source.lastStems[i]).toFloat())}
            for(i in names.indices){val p=File(root,"worst-${if(finite)"B" else "A"}-${names[i]}.f32le");assertFalse(p.exists());p.writeBytes(data[i].array())}
        }
    }
}
