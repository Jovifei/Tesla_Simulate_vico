package com.vico.simulator.sound
import java.io.File
import kotlin.math.*
fun main(args:Array<String>){
 val original=loadProbeBank(File(args[0]));val out=File(args[1]);out.mkdirs()
 File(out,"blend.csv").bufferedWriter().use{w->
 w.write("variant,rpm,load,rms,lower_rms,upper_rms,correlation,cancellation_db,worst_500ms_db,peak,above,clip,nonfinite\n")
 for(variant in listOf("original","crank_origin_rotation")){
 val bank=if(variant=="original") original else original.copy(loops=original.loops.map{loop->
 val phase=(7682.0*loop.rpm/(120.0*48000.0));val offset=round((ceil(phase)-phase)*120.0*48000.0/loop.rpm).toInt()%loop.samples.size
 loop.copy(samples=FloatArray(loop.samples.size){loop.samples[(it+offset)%loop.samples.size]})})
 for(rpm in 700..7200 step 50) for(load in listOf(.32,.62,.92)){
 val renderer=MatlabStatefulBankRenderer(bank);val count=48000*10;val cap=S13RpmBlendCapture(count);renderer.enableRpmBlendCapture(cap)
 val state=SoundState(0.0,rpm.toDouble(),rpm/60.0*4,1.0,load,floatArrayOf(),false,load,load,false,1,1.0,false,false)
 val pcm=renderer.renderReview(state,state,0,count,emptyList())
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
