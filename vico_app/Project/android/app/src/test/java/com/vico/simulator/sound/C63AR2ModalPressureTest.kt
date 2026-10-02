package com.vico.simulator.sound
import com.vico.simulator.sound.s17.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.pow
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
class C63AR2ModalPressureTest {
    @Test fun frozen76Q2TvsS2ReportsLineAndNeighborEnergyAndReplays() {
        val dest=System.getenv("VICO_C63_AR2_MODAL_OUTPUT");Assume.assumeTrue(!dest.isNullOrBlank())
        val root=File(requireNotNull(dest));assertFalse(File(root,"modal.tsv").exists());root.mkdirs()
        val rows=mutableListOf("case\tmode_hz\trpm\tT_center_line_power\tT_line_db\tS2_line_db\tT_neighbor_power\tS2_neighbor_power\tS2_to_T_line_ratio")
        val centers=listOf(540.0,820.0,1100.0,1500.0);val window=FloatArray(48000);val bytes=ByteBuffer.allocate(window.size*4).order(ByteOrder.LITTLE_ENDIAN)
        for(hz in centers)for(k in 1..32){val rpm=15*hz/k;if(rpm !in 700.0..7200.0)continue
            val name="Q2_${hz}_$k";val signal=Array(2){FloatArray(window.size)};val ids=listOf(C63AR2Mode.T,C63AR2Mode.S2)
            for((branch,mode) in ids.withIndex()) {
                val runtime=C63AR2Renderer(C63AR2Profile(),mode,true);var keep=0
                repeat(150){block->val time=block*.02;val state=SoundState(time,rpm,rpm/15,1.0,1.0,floatArrayOf(),false,1.0,1.0)
                    val data=runtime.render(state,960)
                    for(value in data){if(runtime.frames>96000){signal[branch][keep%window.size]=value;keep++}}}
                bytes.clear();signal[branch].forEach{bytes.putFloat(it)}
                File(root,"$name-${mode.name}.f32le").outputStream().buffered(65536).use{it.write(bytes.array())}
                assertEquals(48000,keep)
            }
            val line=C63ModalSpectrum.linePower(signal[0],hz);val dispersed=C63ModalSpectrum.linePower(signal[1],hz)
            val prominenceT=C63ModalSpectrum.prominence(signal[0],hz);val prominenceS=C63ModalSpectrum.prominence(signal[1],hz)
            val sidePower=10.0.pow((prominenceT/10))*line
            val sidePowerS2=10.0.pow((prominenceS/10))*dispersed
            rows.add("$name\t$hz\t$rpm\t$line\t$prominenceT\t$prominenceS\t$sidePower\t$sidePowerS2\t${if(line>0)dispersed/line else 0.0}")
        }
        File(root,"modal.tsv").writeText(rows.joinToString("\n"))
    }
}
