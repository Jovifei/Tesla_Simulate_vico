package com.vico.simulator.sound
import com.vico.simulator.sound.s18.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test

class C63HybridFitFixtureTest {
    @Test fun exportFrozenBaselineAndIndependentBasisForSingleFit() {
        val destination=System.getenv("VICO_C63_HY1_FIXTURE_OUTPUT");Assume.assumeTrue(!destination.isNullOrBlank())
        val root=File(requireNotNull(destination));assertFalse(File(root,"fixture.tsv").exists());root.mkdirs()
        val profile=HybridTestProfiles.create();val rows=mutableListOf("id\tmode\tframes\tprofile\tpeak\traw_arrivals\tdistinct_impulses")
        fun emit(id:String,mode:C63HybridMode,points:List<SoundState>,eventOn:Boolean=true) {
            val renderer=C63HybridRenderer(profile,mode,true,eventOn);val bytes=ByteBuffer.allocate(960*20*8).order(ByteOrder.LITTLE_ENDIAN)
            val pcmBytes=ByteBuffer.allocate(960*4).order(ByteOrder.LITTLE_ENDIAN)
            File(root,"$id.f64le").outputStream().buffered(65536).use{data->
                File(root,"$id.f32le").outputStream().buffered(65536).use{pcm->
                    for(point in points){val samples=renderer.render(point,960);val taps=renderer.qualificationTaps();bytes.clear();pcmBytes.clear()
                        for(i in 0 until 960*20){assertTrue(taps[i].isFinite());bytes.putDouble(taps[i])}
                        samples.forEach{pcmBytes.putFloat(it)};data.write(bytes.array());pcm.write(pcmBytes.array())
                    }
                }
            }
            assertEquals(renderer.frames*20*8,File(root,"$id.f64le").length())
            val ev=renderer.eventObservation();rows.add(id+"\t"+mode+"\t"+renderer.frames+"\t"+profile.identity+"\t"+renderer.peak+"\t"+ev.rawArrivals+"\t"+ev.distinctImpulseFrames)
        }
        fun point(t:Double,r:Double,l:Double)=SoundState(t,r,r/15,l,l,floatArrayOf(),false,l,l)
        for(r in listOf(700.0,1400.0,2200.0,3200.0,4300.0,5500.0,6800.0,7200.0))for(l in listOf(.32,.92))
            emit("steady_"+r+"_"+l,C63HybridMode.T,(0 until 150).map{point(it*.02,r,l)})
        emit("driven_ramp",C63HybridMode.T,(0 until 300).map{point(it*.02,700+6500*it/299.0,.92)})
        emit("event_background",C63HybridMode.E,(0 until 604).map{n->val phase=n%151;val closed=phase in 100..125;point(n*.02,if(closed)4000.0 else 5000.0,if(closed).05 else .9)},false)
        File(root,"fixture.tsv").writeText(rows.joinToString("\n"));assertEquals(19,rows.size)
        println("HY1 fixture emitted18 known synthetic cases; bootstrap response is not a delivery candidate")
    }
}
