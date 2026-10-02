package com.vico.simulator.sound

import com.vico.simulator.sound.s16.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.*
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test

/** Frozen Q0–Q4 fixture copy: separate A/C output; rejected B archive is untouched. */
class C63AudibleQualificationTest {
    private val phoneFrames=mutableListOf<Int>()
    private fun s(t:Double,r:Double,l:Double,h:Double,shift:Boolean=false)=SoundState(t,r,r/60*4,l,l,floatArrayOf(),false,h,l,shiftTrigger=shift)
    private fun phone():List<SoundState> {
        val text=File("E:\\Tesla_speed\\review_packages\\s15-20261001\\device-smoke-performance-fix.json").readText()
        return Regex("\\[\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*\\]").findAll(text).map{m->val v=(1..6).map{m.groupValues[it].toDouble()};require(v[5]==v[5].toInt().toDouble() && v[5]>0 && v[5]<=4800);phoneFrames.add(v[5].toInt());s(v[0],v[1],v[2],v[3],v[4]!=0.0)}.toList()
    }
    @Test fun locked_offline_qualification_complete_even_if_candidate_is_rejected() {
        val destination=System.getenv("VICO_C63_AR1_REGRESSION_OUTPUT");Assume.assumeTrue(!destination.isNullOrBlank())
        val root=File(requireNotNull(destination));assertFalse(File(root,"qualification.tsv").exists());root.mkdirs()
        val rows=mutableListOf("id\tframes\tinput_sha256\tAH_peak\tAR1_peak\tAH_first_exceed\tAR1_first_exceed\tAR1_worst_frame\tAR1_rms_dbfs")
        fun case(id:String,points:List<SoundState>,dump:Boolean=false) {
            val profile=C63AudibleProfile.frozenAR1();val a=C63AudibleRenderer(profile,C63AudibleMode.AH,true);val b=C63AudibleRenderer(profile,C63AudibleMode.SE,true)
            val hash=MessageDigest.getInstance("SHA-256");val input=ByteBuffer.allocate(48).order(ByteOrder.LITTLE_ENDIAN)
            val outA=if(dump)File(root,"$id-AH.f32le").outputStream() else null;val outB=if(dump)File(root,"$id-AR1.f32le").outputStream() else null
            val bytes=ByteBuffer.allocate(4800*4).order(ByteOrder.LITTLE_ENDIAN)
            var frame=0L;var firstA=-1L;var firstB=-1L;var worstB=-1L;var maxB=0.0;var energyB=0.0
            try {
                for((pointIndex,point) in points.withIndex()) {
                    val count=if(id=="Q0_phone" || id=="Q1_phone_plus_hold" && pointIndex<phoneFrames.size)phoneFrames[pointIndex] else 960
                    input.clear();input.putDouble(point.timeS).putDouble(point.rpm).putDouble(point.load).putDouble(point.throttle).putDouble(if(point.shiftTrigger)1.0 else 0.0).putDouble(count.toDouble());hash.update(input.array())
                    val aa=a.render(point,count);val bb=b.render(point,count)
                    for(n in 0 until count) {
                        assertTrue(aa[n].isFinite() && bb[n].isFinite())
                        if(firstA<0 && abs(aa[n])>.8413951416451951)firstA=frame+n
                        if(firstB<0 && abs(bb[n])>.8413951416451951)firstB=frame+n
                        if(abs(bb[n].toDouble())>maxB){maxB=abs(bb[n].toDouble());worstB=frame+n}
                        energyB+=bb[n].toDouble()*bb[n]
                    }
                    if(outA!=null){bytes.clear();aa.forEach{bytes.putFloat(it)};outA.write(bytes.array(),0,count*4)}
                    if(outB!=null){bytes.clear();bb.forEach{bytes.putFloat(it)};outB.write(bytes.array(),0,count*4)}
                    frame+=count
                }
            } finally {outA?.close();outB?.close()}
            rows.add("$id\t$frame\t${hash.digest().joinToString(""){"%02x".format(it)}}\t${a.peak}\t${b.peak}\t$firstA\t$firstB\t$worstB\t${20*log10(sqrt(energyB/frame))}")
        }
        // Q0: exactly32 steady +16 transition + recorded phone, as prior input generator.
        for(r in listOf(700.0,1400.0,2200.0,3200.0,4300.0,5500.0,6800.0,7200.0))for(l in listOf(0.0,.32,.92,1.0))
            case("Q0_steady_${r}_$l",(0 until 150).map{s(it*.02,r,l,l)})
        for(start in listOf(700.0,1800.0,5500.0,7200.0))for(end in listOf(700.0,1800.0,5500.0,7200.0))
            case("Q0_transition_${start}_$end",(0 until 200).map{n->val t=n*.02;val f=((t-.5)/.6).coerceIn(0.0,1.0);s(t,start+(end-start)*f,if(t<2)1.0 else .1,if(t<2)1.0 else .05,n==75)})
        val recorded=phone();case("Q0_phone",recorded,true)
        // Q1 original50Hz trace, explicit fixed shift plan; separate last-state hold.
        val text=File("src/main/assets/s12_v10/c63_w204_v6/common_input_trace.json").readText()
        fun field(name:String)=Regex("\"$name\"\\s*:\\s*([-+0-9.eE]+)").findAll(text).map{it.groupValues[1].toDouble()}.toList()
        val r=field("rpm");val l=field("load");val h=field("throttle");val shifts=doubleArrayOf(6.100416666666667,8.620291666666667,11.1424375);var event=0
        val original=(0 until 1500).map{n->val t=n*.02;val trigger=event<shifts.size && t>=shifts[event];if(trigger)event++;s(t,r[n],l[n],h[n],trigger)}
        case("Q1_original",original,true)
        case("Q1_phone_plus_hold",recorded+(0 until 100).map{recorded.last().copy(timeS=recorded.last().timeS+(it+1)*.02,shiftTrigger=false)})
        // Q2 list determined solely by original mode frequency and valid RPM range.
        for(f in listOf(540.0,820.0,1100.0,1500.0))for(k in 1..32){val rpm=15*f/k;if(rpm>=700 && rpm<=7200)case("Q2_${f}_$k",(0 until 150).map{s(it*.02,rpm,1.0,1.0)})}
        // Q3 bidirectional65s sweep and predefined hot/event/restart trajectories.
        for(up in listOf(true,false))case("Q3_sweep_$up",(0 until 3250).map{n->val f=n/3249.0;s(n*.02,if(up)700+6500*f else 7200-6500*f,1.0,1.0)})
        case("Q3_hot_events",(0 until 600).map{n->val t=n*.02;val high=t<3 || t>=5 && t<8;s(t,if(high)5000.0 else 4000.0,if(high).9 else .05,if(high).9 else .05,n==150 || n==400)},true)
        repeat(3){case("Q3_restart_$it",original.take(250))}
        // Q4 complete frozen boundary combinations, cold vs2s hot conditioning.
        for(rpm in listOf(700.0,1400.0,1849.0,1850.0,1851.0))for(load in listOf(0.0,.2,.32,.5,1.0))for(throttle in listOf(0.0,.2,.35,1.0))for(hot in listOf(false,true)) {
            val warm=if(hot)(0 until 100).map{s(-2+it*.02,5000.0,.9,.9)} else emptyList()
            case("Q4_${rpm}_${load}_${throttle}_$hot",warm+(0 until 150).map{s(it*.02,rpm,load,throttle)})
        }
        File(root,"qualification.tsv").writeText(rows.joinToString("\n"))
        println("Locked qualification emitted ${rows.size-1} cases; inspect every numerical and protection gate before installing")
    }
}
