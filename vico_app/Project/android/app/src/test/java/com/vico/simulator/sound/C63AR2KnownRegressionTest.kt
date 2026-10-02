package com.vico.simulator.sound
import com.vico.simulator.sound.s17.*
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
import java.io.File
import kotlin.math.*

class C63AR2KnownRegressionTest {
    private fun s(t:Double,r:Double,l:Double,h:Double,event:Boolean=false)=SoundState(t,r,r/60*4,l,l,floatArrayOf(),false,h,l,shiftTrigger=event)
    @Test fun frozen_holdout_single_scalar_no_recalibration() {
        val dest=System.getenv("VICO_C63_AR2_KNOWN297_OUTPUT");Assume.assumeTrue(!dest.isNullOrBlank())
        val root=File(requireNotNull(dest));root.mkdirs();val report=File(root,"holdout.tsv");assertFalse(report.exists())
        val manifest=File("E:\\Tesla_speed\\review_packages\\s15-ah-20261002\\holdout-manifest.json").readText()
        val list=Regex("\"rpms\"\\s*:\\s*\\[([^]]*)]",RegexOption.DOT_MATCHES_ALL).find(manifest)!!.groupValues[1].split(',').map{it.trim().toDouble()}
        val rows=mutableListOf("id\tframes\tAH_peak\tAR2_peak\tscalar_max_difference\tpass")
        fun case(id:String,points:List<SoundState>) {
            val profile=C63AR2Profile();val a=C63AR2Renderer(profile,C63AR2Mode.AH,true);val c=C63AR2Renderer(profile,C63AR2Mode.SE2,true)
            var error=0.0
            for(point in points){val aa=a.render(point,960);val cc=c.render(point,960);for(i in cc.indices)error=max(error,abs(cc[i]-aa[i].toDouble()))}
            rows.add("$id\t${c.frames}\t${a.peak}\t${c.peak}\t$error\t${c.peak<=.8413951416451951}")
        }
        for((i,r) in list.withIndex())case("H1_$i",(0 until 250).map{s(it*.02,r,1.0,1.0)})
        for(duration in listOf(.12,1.5,12.0))for(hot in listOf(false,true)) {
            val points=mutableListOf<SoundState>();var t=0.0
            if(hot)repeat(100){points.add(s(t,5000.0,.9,.9));t+=.02}
            val rpms=listOf(700.0,2050.0,4100.0,6150.0,7200.0,700.0)
            for(i in 0 until rpms.size-1){val count=(duration/.02).roundToInt()
                repeat(count){n->points.add(s(t,rpms[i]+(rpms[i+1]-rpms[i])*(n+1)/count,1.0,1.0));t+=.02}
                repeat(50){points.add(s(t,rpms[i+1],1.0,1.0));t+=.02}
            }
            case("H2_${duration}_$hot",points)
        }
        val events=(0 until 450).map{n->val t=n*.02;when{t<2->s(t,700.0,.14,.14);t<5->s(t,5000.0,.9,.9);t<6->s(t,4000.0,.05,.05,n==250);t<8->s(t,4000.0,.8,.8);else->s(t,3000.0,.05,.05,n==400)}}
        case("H3_events",events)
        report.writeText(rows.joinToString("\n"))
        println("Holdout cases=${rows.size-1}; inspect pass flags, no parameter change permitted")
    }
}



