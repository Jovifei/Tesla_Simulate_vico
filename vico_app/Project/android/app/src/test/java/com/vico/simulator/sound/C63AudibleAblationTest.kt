package com.vico.simulator.sound
import com.vico.simulator.sound.s16.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
class C63AudibleAblationTest {
    @Test fun fixedHotEpisodeBranchesAreMeasuredWithoutChangingProfile() {
        val destination=System.getenv("VICO_C63_AR1_ABLATION_OUTPUT");Assume.assumeTrue(!destination.isNullOrBlank())
        val root=File(requireNotNull(destination));assertFalse(File(root,"episodes.tsv").exists());root.mkdirs()
        val rows=mutableListOf("mode\tframes\tafterfire_events\tpeak")
        for(mode in C63AudibleMode.values()) {
            val profile=C63AudibleProfile.frozenAR1();val source=C63AudibleSource(profile,mode);val runtime=C63AudibleRenderer(profile,mode,true)
            val bytes=ByteBuffer.allocate(960*4).order(ByteOrder.LITTLE_ENDIAN)
            val fireBytes=ByteBuffer.allocate(960*4).order(ByteOrder.LITTLE_ENDIAN)
            File(root,"$mode.f32le").outputStream().buffered(65536).use{mixed->
                File(root,"$mode-afterfire.f32le").outputStream().buffered(65536).use{fire->
                    repeat(600){n->val time=n*.02;val high=time<3 || time>=5 && time<8;val rpm=if(high)5000.0 else 4000.0;val load=if(high).9 else .05
                        val input=SoundState(time,rpm,rpm/15,load,load,floatArrayOf(),false,load,load,shiftTrigger=n==150 || n==400)
                        bytes.clear();runtime.render(input,960).forEach{bytes.putFloat(it)};mixed.write(bytes.array())
                        fireBytes.clear();repeat(960){source.sample(rpm,load,load);fireBytes.putFloat(source.lastStems[4].toFloat())};fire.write(fireBytes.array())
                    }
                }
            }
            rows.add("$mode\t576000\t${source.afterfireEvents}\t${runtime.peak}")
        }
        File(root,"episodes.tsv").writeText(rows.joinToString("\n"))
    }
}
