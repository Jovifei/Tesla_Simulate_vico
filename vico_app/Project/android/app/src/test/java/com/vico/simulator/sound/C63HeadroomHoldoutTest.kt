package com.vico.simulator.sound
import com.vico.simulator.sound.s15.*
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test
import java.io.File
import kotlin.math.*

class C63HeadroomHoldoutTest {
    private fun s(t:Double,r:Double,l:Double,h:Double,event:Boolean=false)=SoundState(t,r,r/60*4,l,l,floatArrayOf(),false,h,l,shiftTrigger=event)
    @Test fun frozen_holdout_single_scalar_no_recalibration() {
        val dest=System.getenv("VICO_S15_AH_OUTPUT");Assume.assumeTrue(!dest.isNullOrBlank())
        val root=File(requireNotNull(dest));root.mkdirs();val report=File(root,"holdout.tsv");assertFalse(report.exists())
        val manifest=File("E:\\Tesla_speed\\review_packages\\s15-ah-20261002\\holdout-manifest.json").readText()
        val list=Regex("\"rpms\"\\s*:\\s*\\[([^]]*)]",RegexOption.DOT_MATCHES_ALL).find(manifest)!!.groupValues[1].split(',').map{it.trim().toDouble()}
        val rows=mutableListOf("id\tframes\tA_peak\tC_peak\tscalar_max_error\tpass")
        fun case(id:String,points:List<SoundState>) {
            val a=C63RuntimeRenderer(true,false,false);val c=C63RuntimeRenderer(true,false,true)
            var error=0.0
            for(point in points){val aa=a.render(point,960);val cc=c.render(point,960);for(i in cc.indices)error=max(error,abs(cc[i]-C63HeadroomProfile.SCALAR*aa[i]))}
            rows.add("$id\t${c.frames}\t${a.peak}\t${c.peak}\t$error\t${c.peak<=.8413951416451951 && error<=1e-6}")
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
    @Test fun snapshot_and_warmup_isolation_preserve_c_initial_state() {
        val a=C63RuntimeRenderer(false,false,true);repeat(20){a.render(s(it*.02,4000.0,.4,.4),960)}
        val b=C63RuntimeRenderer(false,false,true);b.restore(a.snapshot())
        repeat(50){val p=s(1+it*.02,4000.0,.05,.05);assertArrayEquals(a.render(p,960),b.render(p,960),0f)}
        val cold=C63RuntimeRenderer(false,false,true)
        C63RuntimePreparation.warmup()
        val fresh=C63RuntimeRenderer(false,false,true);assertArrayEquals(cold.render(s(0.0,2000.0,.5,.5),960),fresh.render(s(0.0,2000.0,.5,.5),960),0f)
    }
    @Test fun identical_control_points_and_events_are_independent_of_output_block_size() {
        fun run(block:Int):FloatArray {
            val runtime=C63RuntimeRenderer(false,false,true);val result=FloatArray(240000);var frame=0
            for(point in 0 until 250) {
                val state=s(point*.02,if(point<125)4000.0 else 3000.0,if(point<125).4 else .05,if(point<125).4 else .05,point==75 || point==175)
                var remaining=960
                while(remaining>0){val count=minOf(block,remaining);val chunk=runtime.render(state,count);chunk.copyInto(result,frame);frame+=count;remaining-=count}
            }
            return result
        }
        val reference=run(960)
        for(block in listOf(96,192,240,256,480))assertArrayEquals(reference,run(block),0f)
    }
    @Test fun recorded_phone_repeated_timestamps_and_frame_counts_survive_partitioning() {
        val text=File("E:\\Tesla_speed\\review_packages\\s15-20261001\\device-smoke-performance-fix.json").readText()
        val rows=Regex("\\[\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*\\]").findAll(text).map{m->(1..6).map{m.groupValues[it].toDouble()}}.toList()
        assertTrue(rows.isNotEmpty())
        fun run(block:Int):FloatArray {
            val runtime=C63RuntimeRenderer(false,false,true);val result=FloatArray(rows.sumOf{it[5].toInt()});var frame=0
            for(v in rows){require(v[5]==v[5].toInt().toDouble());val state=s(v[0],v[1],v[2],v[3],v[4]!=0.0);var remaining=v[5].toInt()
                while(remaining>0){val count=minOf(block,remaining);runtime.render(state,count).copyInto(result,frame);frame+=count;remaining-=count}}
            return result
        }
        val reference=run(960)
        for(block in listOf(96,192,240,256,480))assertArrayEquals(reference,run(block),0f)
    }
}
