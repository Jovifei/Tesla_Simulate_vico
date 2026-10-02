package com.vico.simulator.sound
import com.vico.simulator.sound.s17.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
class C63AR2EpisodeQualificationTest {
    @Test fun fixedHotClosureRecoveryAndShiftScenariosAcrossAllFiveBranches() {
        val destination=System.getenv("VICO_C63_AR2_EPISODE_OUTPUT");Assume.assumeTrue(!destination.isNullOrBlank())
        val root=File(requireNotNull(destination));assertFalse(File(root,"episodes.tsv").exists());root.mkdirs()
        val modes=C63AR2Mode.values();val rows=mutableListOf("mode\tframes\traw_arrivals\tdistinct_impulses\tepisodes\tpeak\tstopreason")
        for(mode in modes) {
            val renderer=C63AR2Renderer(C63AR2Profile(),mode,true);var frame=0;var peak=0.0
            val out=File(root,"$mode.f32le");val eventBytes=ByteBuffer.allocate(960*4).order(ByteOrder.LITTLE_ENDIAN)
            val stem=File(root,"$mode-afterfire-stem.f32le")
            stem.outputStream().buffered(65536).use{firePcm->
            out.outputStream().buffered(65536).use{pcm->
                repeat(604){point->
                    val phase=point%151
                    val (rpm,load,throttle)=when {
                        phase<100 -> Triple(5000.0,.9,.9)
                        phase<126 -> Triple(4000.0,.05,.05)
                        else -> Triple(5000.0,.9,.9)
                    }
                    val input=SoundState(frame/48000.0,rpm,rpm/15,load,load,floatArrayOf(),false,throttle,load,shiftTrigger=phase==110 || phase==200)
                    val samples=renderer.render(input,960)
                    eventBytes.clear()
                    for(value in samples){peak=maxOf(peak,kotlin.math.abs(value.toDouble()));eventBytes.putFloat(value)}
                    pcm.write(eventBytes.array())
                    eventBytes.clear()
                    val fire=renderer.snapshot().fireBlock
                    for(n in samples.indices)eventBytes.putFloat(fire[n].toFloat())
                    firePcm.write(eventBytes.array())
                    frame+=960
                }
            }
            }
            assertEquals(frame*4L,stem.length())
            val observation=renderer.eventObservation()
            val eventRows=mutableListOf("kind\tframe\tamplitude")
            observation.arrivalFrames.indices.forEach{eventRows.add("raw_arrival\t"+observation.arrivalFrames[it]+"\t"+observation.arrivalAmplitudes[it])}
            observation.impulseFrames.indices.forEach{eventRows.add("distinct_impulse\t"+observation.impulseFrames[it]+"\t"+observation.impulseAmplitudes[it])}
            File(root,"$mode-events.tsv").writeText(eventRows.joinToString("\n"))
            rows.add(mode.name+"\t"+frame+"\t"+observation.rawArrivals+"\t"+observation.distinctImpulseFrames+"\t"+observation.episodes+"\t"+peak+"\tSTOP_AFTER_FIXED_TRACE")
        }
        File(root,"episodes.tsv").writeText(rows.joinToString("\n"))
    }
}
