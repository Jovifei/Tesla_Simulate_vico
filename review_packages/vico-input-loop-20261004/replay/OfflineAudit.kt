package com.vico.simulator.sound
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*

private fun floats(file:File,a:FloatArray){val b=ByteBuffer.allocate(a.size*4).order(ByteOrder.LITTLE_ENDIAN);for(x in a)b.putFloat(x);file.writeBytes(b.array())}
private fun state(t:Double,rpm:Double,load:Double)=SoundState(t,rpm,rpm/60*4,max(.08,load),load,floatArrayOf(),false,load,load)
private fun saveStats(dir:File,s:S13MixSnapshot){File(dir,"stats.tsv").writeText("evaluatedFrames\tpreClipPeak\taboveContractFrames\thardClipFrames\tnonFiniteFrames\tloadOutOfBankFrames\trpmOutOfBankFrames\trejectedInputBlocks\n${s.evaluatedFrames}\t${s.preClipPeak}\t${s.aboveContractFrames}\t${s.hardClipFrames}\t${s.nonFiniteFrames}\t${s.loadOutOfBankFrames}\t${s.rpmOutOfBankFrames}\t${s.rejectedInputBlocks}\n")}
private fun grid(bank:MatlabSoundBank,out:File,name:String,rpm0:Double,rpm1:Double,load:Double,seconds:Double){
 val dir=File(out,name);dir.mkdirs();val n=(seconds*bank.sampleRateHz).toInt();val renderer=MatlabStatefulBankRenderer(bank);val capture=S13RpmBlendCapture(n);renderer.enableRpmBlendCapture(capture);val output=FloatArray(n)
 var offset=0
 while(offset<n){val count=min(960,n-offset);fun at(frame:Int):SoundState{val r=rpm0+(rpm1-rpm0)*frame/n.toDouble();return state(frame/48000.0,r,load)}
  val block=renderer.renderReview(at(offset),at(offset+count),offset,count,emptyList());block.copyInto(output,offset);offset+=count}
 check(capture.frameCount==n)
 floats(File(dir,"output.f32"),output);floats(File(dir,"lower.f32"),capture.lowerPath);floats(File(dir,"upper.f32"),capture.upperPath);floats(File(dir,"weight.f32"),capture.rpmWeight);floats(File(dir,"shared_gain.f32"),capture.sharedGain);floats(File(dir,"event.f32"),capture.eventContribution)
 File(dir,"lower_index.u8").writeBytes(capture.rpmLowerIndex);File(dir,"upper_index.u8").writeBytes(capture.rpmUpperIndex);saveStats(dir,renderer.mixStats())
 File(dir,"case.tsv").writeText("name\tkind\tframes\trpm0\trpm1\tload\n$name\t${if(rpm0==rpm1)"constant" else "sweep"}\t$n\t$rpm0\t$rpm1\t$load\n")
 println("GRID $name ${renderer.mixStats()}")
}
private fun trajectory(bank:MatlabSoundBank,out:File,peakKmh:Double,legacy:Boolean){
 val name="drive_${peakKmh.toInt()}_${if(legacy)"legacy_events" else "qualified_events"}";val dir=File(out,name);dir.mkdirs()
 val renderer=MatlabStatefulBankRenderer(bank);val controller=MatlabPowertrainController(bank.powertrain);val n=1440000;val output=FloatArray(n);var shifts=0;var fires=0
 File(dir,"controls.tsv").bufferedWriter().use{csv->
  csv.write("time_s\tspeed_kmh\taccel_mps2\tdemand_proxy\trpm\tload\tgear\tshift\tafterfire\tshift_gain\tcause\n")
  for(i in 0 until 1500){val t=i*.02;val speed=when{t<2->0.0;t<12->peakKmh*(t-2)/10;t<20->peakKmh;t<28->peakKmh*(28-t)/8;else->0.0};val accel=when{t<2->0.0;t<12->peakKmh/3.6/10;t<20->0.0;t<28->-peakKmh/3.6/8;else->0.0};val demand=(accel/3).coerceIn(0.0,1.0);val ns=1_000_000_000L+i*20_000_000L
   val c=DriveInputControl(DriveInputSource.REAL,1,ns+250_000_000,true,true,ns,ns,i+1L,ns)
   val p=if(legacy)controller.update(t,speed,accel,demand) else controller.updateMeasured(t,speed,accel,demand,c)
   val s=SoundState(timeS=t,rpm=p.rpm,frequencyHz=p.rpm/60*4,amplitude=max(.08,p.load),brightness=p.load,harmonics=floatArrayOf(),muted=false,throttle=demand,load=p.load,braking=accel < -1.2,gear=p.gear,shiftGain=p.torqueGain,afterfireTrigger=p.afterfireTrigger,shiftTrigger=p.shiftTrigger,inputControl=c,afterfireCauseCode=p.afterfireCauseCode,afterfireSourceId=p.afterfireSourceId,modelSpeedKmh=speed,modelAccelerationMps2=accel)
   renderer.render(s,960).copyInto(output,i*960);if(p.shiftTrigger)shifts++;if(p.afterfireTrigger)fires++
   csv.write("$t\t$speed\t$accel\t$demand\t${p.rpm}\t${p.load}\t${p.gear}\t${if(p.shiftTrigger)1 else 0}\t${if(p.afterfireTrigger)1 else 0}\t${p.torqueGain}\t${p.afterfireCauseCode}\n")
  }
 }
 floats(File(dir,"output.f32"),output);saveStats(dir,renderer.mixStats());File(dir,"case.tsv").writeText("name\tkind\tframes\tpeak_kmh\tlegacy\tshifts\tafterfires\n$name\tdrive\t$n\t$peakKmh\t$legacy\t$shifts\t$fires\n")
 println("DRIVE $name shifts=$shifts afterfires=$fires ${renderer.mixStats()}")
}
fun main(args:Array<String>){
 val bank=readBank(File(args[0]));val out=File(args[1]);out.mkdirs()
 val levels=(bank.rpmLevels.toList()+bank.rpmLevels.toList().zipWithNext{a,b->(a+b)/2}).sorted()
 for(load in listOf(.32,.62,.92)){
  for(rpm in levels)grid(bank,out,"constant_${rpm.toInt()}_${(load*100).roundToInt()}",rpm,rpm,load,2.5)
  grid(bank,out,"sweep_up_${(load*100).roundToInt()}",700.0,7200.0,load,10.0)
  grid(bank,out,"sweep_down_${(load*100).roundToInt()}",7200.0,700.0,load,10.0)
 }
 for(peak in listOf(70.0,75.0))for(legacy in listOf(false,true))trajectory(bank,out,peak,legacy)
}
