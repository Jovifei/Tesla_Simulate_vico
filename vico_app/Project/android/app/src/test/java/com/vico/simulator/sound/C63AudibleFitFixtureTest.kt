package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63IdleRuntime
import com.vico.simulator.sound.s16.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
class C63AudibleFitFixtureTest {
    @Test fun exportAhOutputForVectorOutputEquivalence() {
        val destination=System.getenv("VICO_C63_AR1_FIT_EQ_OUTPUT");Assume.assumeTrue(!destination.isNullOrBlank())
        val root=File(requireNotNull(destination));root.mkdirs()
        for((name,rpm,load) in listOf(Triple("low",1100.0,.27),Triple("mid",2900.0,.64),Triple("pull",4700.0,.87),Triple("high",6100.0,.93))) {
            val file=File(root,"$name-AH.f32le");assertFalse(file.exists())
            val runtime=C63AudibleRenderer(C63AudibleProfile(),C63AudibleMode.AH)
            val bytes=ByteBuffer.allocate(960*4).order(ByteOrder.LITTLE_ENDIAN)
            file.outputStream().buffered(65536).use{stream->repeat(250){n->
                val state=SoundState(n*.02,rpm,rpm/15,load,load,floatArrayOf(),false,load,load)
                bytes.clear();runtime.render(state,960).forEach{bytes.putFloat(it)};stream.write(bytes.array())}}
        }
    }
    @Test fun exportIndependentSustainedCalibrationControlsOnly() {
        val destination=System.getenv("VICO_C63_AR1_FIT_FIXTURE_OUTPUT");Assume.assumeTrue(!destination.isNullOrBlank())
        val root=File(requireNotNull(destination));assertFalse(File(root,"fixture.tsv").exists());root.mkdirs()
        val groups=listOf(Triple("low",1100.0,.27),Triple("mid",2900.0,.64),Triple("pull",4700.0,.87),Triple("high",6100.0,.93))
        val rows=mutableListOf("group\trpm\tload\tthrottle\tframes\tstudy_start_frame\tclock_scope")
        for((name,rpm,load) in groups) {
            val source=C63AudibleSource(C63AudibleProfile(),C63AudibleMode.AH);val idle=C63IdleRuntime();val box=C63MechanicalTexture(1.0)
            var phase=0.0;var lastEvent=-1L
            val buffer=ByteBuffer.allocate(11*8).order(ByteOrder.LITTLE_ENDIAN)
            File(root,"$name.f64le").outputStream().buffered(65536).use{stream->
                repeat(240000){
                    source.sample(rpm,load,load);phase+=rpm/(60*48000.0);val event=floor(phase*4).toLong()
                    val impulse=if(event!=lastEvent)min((3000/max(rpm,850.0)).pow(1.2),2.0)*(.45+.55*load) else 0.0
                    lastEvent=event;buffer.clear();source.lastStems.forEach{buffer.putDouble(it)}
                    buffer.putDouble(impulse);buffer.putDouble(box.sample());buffer.putDouble(idle.sample(rpm,load,load))
                    buffer.putDouble(.0045*(.4+.6*load)*sin(2*PI*phase)*.75);stream.write(buffer.array())
                }
            }
            rows.add("$name\t$rpm\t$load\t$load\t240000\t96000\tINDEPENDENT_DIAGNOSTIC_NOT_REFERENCE_RPM_LABEL")
        }
        File(root,"fixture.tsv").writeText(rows.joinToString("\n"))
        File(root,"columns.txt").writeText("exhaust,bark,intake,mechanical,afterfire,body,rumble,impulse,unscaled_box,idle,mechanical_carrier")
    }
}
