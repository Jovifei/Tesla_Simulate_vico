package com.vico.simulator.sound
import com.vico.simulator.sound.s16.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
class C63AudibleModalProbeTest {
    @Test fun frozenOriginalQ2PressureCasesAreMeasuredWithoutRefit() {
        val destination=System.getenv("VICO_C63_AR1_MODAL_OUTPUT");Assume.assumeTrue(!destination.isNullOrBlank())
        val root=File(requireNotNull(destination));assertFalse(File(root,"cases.tsv").exists());root.mkdirs()
        val rows=mutableListOf("id\tmode_hz\trpm\tframes")
        for(hz in listOf(540.0,820.0,1100.0,1500.0))for(k in 1..32) {
            val rpm=15*hz/k;if(rpm<700 || rpm>7200)continue
            val name="Q2_${hz}_$k"
            for(mode in listOf(C63AudibleMode.AH,C63AudibleMode.S)) {
                val runtime=C63AudibleRenderer(C63AudibleProfile.frozenAR1(),mode,true)
                val bytes=ByteBuffer.allocate(960*4).order(ByteOrder.LITTLE_ENDIAN)
                File(root,"$name-$mode.f32le").outputStream().buffered(65536).use{stream->repeat(150){n->
                    val input=SoundState(n*.02,rpm,rpm/15,1.0,1.0,floatArrayOf(),false,1.0,1.0)
                    bytes.clear();runtime.render(input,960).forEach{bytes.putFloat(it)};stream.write(bytes.array())}}
            }
            rows.add("$name\t$hz\t$rpm\t144000")
        }
        File(root,"cases.tsv").writeText(rows.joinToString("\n"))
    }
}
