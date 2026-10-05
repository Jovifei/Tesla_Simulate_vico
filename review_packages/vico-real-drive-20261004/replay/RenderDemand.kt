package com.vico.simulator.sound
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*
fun main(args:Array<String>){
 val assets=File(args[0]);val out=File(args[1]);out.mkdirs();var budgetFailures=0
 for(peak in listOf(20.0,40.0,70.0,75.0,100.0,144.0)) {
  val bank=loadProbeBank(assets);val renderer=MatlabStatefulBankRenderer(bank);val model=MatlabPowertrainController(bank.powertrain)
  val dir=File(out,"drive_${peak.toInt()}");dir.mkdirs();val rows=File(dir,"states.csv").bufferedWriter();rows.write("t,speed,accel,throttle_proxy,bank_load,gear,rpm,shift_gain,shift,afterfire,cause\n")
  val pcm=File(dir,"pcm.f32le").outputStream();var sum=0.0;var maxAbs=0.0;var shifts=0;var fires=0
  for(block in 0 until 2000){
   val t=block*.02
   val speed=when{t<2->0.0;t<14->peak*(t-2)/12;t<26->peak;t<38->peak*(38-t)/12;else->0.0}
   val accel=when{t<2->0.0;t<14->peak/3.6/12;t<26->0.0;t<38->-peak/3.6/12;else->0.0}
   val n=1_000_000_000L+(t*1e9).toLong();val gps=1_000_000_000L+(floor(t)*1e9).toLong()
   // Sample-and-hold GPS at 1Hz; IMU at50Hz. Source speed follows the time of the held GPS.
   val gt=floor(t);val gv=when{gt<2->0.0;gt<14->peak*(gt-2)/12;gt<26->peak;gt<38->peak*(38-gt)/12;else->0.0}
   val throttle=(accel/3).coerceIn(0.0,1.0)
   val control=DriveInputControl(DriveInputSource.REAL,1,n+250_000_000L,true,true,n,gps,block.toLong()+1,n)
   val measuredControl=probeControl(control)
   val state=model.updateMeasured(t,gv,accel,throttle,measuredControl)
   val proxy=probeDemand(state,throttle)
   val sound=probeMap(state,DrivePoint(t,gv,throttle,accel,accel< -1.2),measuredControl)
   val wave=renderer.render(sound,960)
   val bytes=ByteBuffer.allocate(wave.size*4).order(ByteOrder.LITTLE_ENDIAN)
   for(x in wave){bytes.putFloat(x);sum+=x*x;maxAbs=max(maxAbs,abs(x.toDouble()))};pcm.write(bytes.array())
   if(state.shiftTrigger)shifts++;if(state.afterfireTrigger)fires++
   rows.write("$t,$gv,$accel,$proxy,${state.load},${state.gear},${state.rpm},${state.torqueGain},${state.shiftTrigger},${state.afterfireTrigger},${state.afterfireCauseCode}\n")
  }
  pcm.close();rows.close();val stats=renderer.mixStats();File(dir,"stats.txt").writeText("$stats\nrms=${sqrt(sum/(40*48000))} peak=$maxAbs shifts=$shifts afterfires=$fires\n");println("peak=$peak $stats");if(stats.hardClipFrames!=0L||stats.nonFiniteFrames!=0L||stats.aboveContractFrames!=0L)budgetFailures++
 }
 check(budgetFailures==0){"Raw mix budget failed in $budgetFailures cases"}
}
