package com.vico.simulator.sound
import java.io.File
import kotlin.math.*
fun main(args:Array<String>){
 val original=loadProbeBank(File(args[0]));val out=File(args[1]);out.mkdirs()
 File(out,"blend.csv").bufferedWriter().use{w->
 w.write("variant,rpm,load,rms,lower_rms,upper_rms,correlation,cancellation_db,worst_500ms_db,peak,above,clip,nonfinite\n")
 for(variant in listOf("original","rpm_guards_v1")){
 val bank=if(variant=="original") original else original.copy(loops=original.loops+listOf(5400,5600).flatMap{rpm->listOf(.32,.92).map{load->val name="rpm_${rpm}_load_${(load*100).roundToInt()}.wav";MatlabLoop(rpm.toDouble(),load,FloatWavDecoder.decode(File(File(args[0],"candidate"),name).readBytes()).samples)}})
 for(rpm in listOf(5200,5500,6100,5450,5550,5250,5750,6050,6250)) for(load in listOf(.32,.47,.77,.92)){
 val renderer=MatlabStatefulBankRenderer(bank);val count=48000*4;val cap=S13RpmBlendCapture(count);renderer.enableRpmBlendCapture(cap)
 val state=SoundState(0.0,rpm.toDouble(),rpm/60.0*4,1.0,load,floatArrayOf(),false,load,load,false,1,1.0,false,false)
 val pcm=renderer.renderReview(state,state,0,count,emptyList())
 val tail=java.nio.ByteBuffer.allocate(48000*3*4).order(java.nio.ByteOrder.LITTLE_ENDIAN);for(i in count-48000*3 until count)tail.putFloat(pcm[i]);File(out,"${variant}_${rpm}_${(load*100).roundToInt()}.f32le").writeBytes(tail.array())
 var aa=0.0;var bb=0.0;var ab=0.0;var pp=0.0;var worst=0.0
 for(start in 0 until count step 24000){var a=0.0;var b=0.0;var p=0.0
 for(i in start until min(start+24000,count)){val x=cap.lowerPath[i].toDouble();val y=cap.upperPath[i].toDouble();a+=x*x;b+=y*y;ab+=x*y;p+=pcm[i].toDouble()*pcm[i]}
 aa+=a;bb+=b;pp+=p;val q=cap.rpmWeight[start].toDouble();val coherent=(1-q)*sqrt(a)+q*sqrt(b);if(coherent>0)worst=min(worst,20*log10(sqrt(p)/coherent))}
 val q=cap.rpmWeight[0].toDouble();val coherent=(1-q)*sqrt(aa)+q*sqrt(bb);val db=20*log10(sqrt(pp)/coherent);val st=renderer.mixStats()
 w.write("$variant,$rpm,$load,${sqrt(pp/count)},${sqrt(aa/count)},${sqrt(bb/count)},${ab/sqrt(aa*bb)},$db,$worst,${st.preClipPeak},${st.aboveContractFrames},${st.hardClipFrames},${st.nonFiniteFrames}\n")
 }
 w.flush();println("finished $variant")
 }
 }
}
