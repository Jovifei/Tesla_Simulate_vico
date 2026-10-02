package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63RuntimeRenderer
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test

/** Offline pre-clip measurements only. No unchecked PCM is sent to AudioTrack. */
class C63QualificationTest {
    private fun state(t:Double,r:Double,l:Double,h:Double,shift:Boolean=false)=SoundState(t,r,r/60*4,l,l,floatArrayOf(),false,h,l,shiftTrigger=shift)
    @Test fun fixed_safety_set_peak_inventory() {
        val destination=System.getenv("VICO_S15_QUALIFICATION")
        Assume.assumeTrue(!destination.isNullOrBlank())
        val rows=mutableListOf<String>()
        fun run(id:String,states:List<SoundState>) {
            val runtime=C63RuntimeRenderer(true)
            for(s in states) assertTrue(runtime.render(s,960).all{it.isFinite()})
            rows.add("$id\t${runtime.frames}\t${runtime.peak}")
        }
        for(r in listOf(700.0,1400.0,2200.0,3200.0,4300.0,5500.0,6800.0,7200.0)) for(l in listOf(0.0,.32,.92,1.0))
            run("steady_${r}_$l",(0 until 150).map{state(it*.02,r,l,l)})
        for(start in listOf(700.0,1800.0,5500.0,7200.0)) for(end in listOf(700.0,1800.0,5500.0,7200.0)) {
            run("transition_${start}_$end",(0 until 200).map{n->
                val t=n*.02; val fraction=((t-.5)/.6).coerceIn(0.0,1.0)
                state(t,start+(end-start)*fraction,if(t<2)1.0 else .1,if(t<2)1.0 else .05,n==75)
            })
        }
        val text=java.io.File("E:\\Tesla_speed\\review_packages\\s15-20261001\\device-smoke-performance-fix.json").readText()
        val points=Regex("\\[\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*\\]").findAll(text).map{m->(1..6).map{m.groupValues[it].toDouble()}}.toList()
        run("recorded_phone",points.map{state(it[0],it[1],it[2],it[3],it[4]!=0.0)})
        val path=java.nio.file.Paths.get(requireNotNull(destination));assertFalse(java.nio.file.Files.exists(path))
        java.nio.file.Files.write(path,("id\tframes\tpreclip_peak\n"+rows.joinToString("\n")).toByteArray())
    }
}
