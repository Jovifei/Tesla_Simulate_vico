package com.vico.simulator.sound
import java.io.File
import kotlin.math.*
fun main(args:Array<String>){
 val bank=loadProbeBank(File(args[0]))
 for(mode in listOf("stop","watchdog")){
  val renderer=MatlabStatefulBankRenderer(bank)
  val afterfireIndex=renderer.javaClass.getDeclaredField("afterfireIndex").also{it.isAccessible=true}
  val activeShift=renderer.javaClass.getDeclaredField("activeShift").also{it.isAccessible=true}
  val model=MatlabPowertrainController(bank.powertrain);val gate=AudioInputGate();val envelope=GainEnvelope()
  var last:SoundState?=null;var endPeak=Double.NaN;var tailEvents=0;var pendingAfterfireIndex=0.0
  for(i in 0 until 70){val t=i*.02;val n=1_000_000_000L+(t*1e9).toLong();val active=i<40;val running=mode!="stop"||active
   val ctl=probeControl(DriveInputControl(DriveInputSource.REAL,1,if(active)n+1_000_000_000L else 1L,true,true,n,n,controlTimeElapsedNanos=n))
   val p=model.updateMeasured(t,75.0,1.5,.5,ctl)
   val live=probeMap(p,DrivePoint(t,75.0,.5,1.5),ctl).copy(afterfireTrigger=i==39,shiftTrigger=false)
   // Queue fixture deliberately starts one known transient immediately before the stop/deadline edge.
   val state=selectAudioWriterSnapshot(running,live,last)!!
   val decision=gate.evaluate(state.inputControl,state.timeS,n,running)
   if(decision.clearTransients)renderer.clearTransientEvents()
   val audible=active&&running&&decision.usable
   val gain=envelope.step(audible)
   val selected=if(audible)state.copy(afterfireTrigger=state.afterfireTrigger&&decision.allowEvents) else requireNotNull(last).copy(afterfireTrigger=false,shiftTrigger=false,shiftGain=1.0)
   if(audible)last=selected.copy(afterfireTrigger=false,shiftTrigger=false,shiftGain=1.0)
   val wave=renderer.render(selected,960)
   if(i==39)pendingAfterfireIndex=afterfireIndex.getInt(renderer).toDouble()
   if(i>=40 && (afterfireIndex.getInt(renderer)>=0 || activeShift.get(renderer)!=null))tailEvents++
   endPeak=wave.maxOf{abs(it.toDouble())}*gain
  }
  check(pendingAfterfireIndex>0);check(tailEvents==0);check(endPeak==0.0);val stats=renderer.mixStats();check(stats.hardClipFrames==0L&&stats.nonFiniteFrames==0L&&stats.aboveContractFrames==0L)
  println("$mode pendingAfterfireIndex=$pendingAfterfireIndex tailEvents=$tailEvents endOutputPeak=$endPeak $stats")
 }
 if(probeHasRevision()) {
  val renderer=MatlabStatefulBankRenderer(bank);val model=MatlabPowertrainController(bank.powertrain);val gate=AudioInputGate()
  val afterfireIndex=renderer.javaClass.getDeclaredField("afterfireIndex").also{it.isAccessible=true}
  val activeShift=renderer.javaClass.getDeclaredField("activeShift").also{it.isAccessible=true}
  var old:SoundState?=null;var oldRevision=0L
  for(i in 0..43){val t=i*.02;val n=1_000_000_000L+(t*1e9).toLong();val control=probeControl(DriveInputControl(DriveInputSource.REAL,9,n+1_000_000_000L,true,true,n,n,controlTimeElapsedNanos=n))
   if(i==40){val bad=control.copy(imuSampleElapsedNanos=n-400_000_000L);val rejected=model.updateMeasured(t,75.0,1.5,.5,bad).let{probeMap(it,DrivePoint(t,75.0,.5,1.5),bad)};check(!requireNotNull(rejected.inputControl).usable)}
   val state=if(i==40)requireNotNull(old) else model.updateMeasured(t,75.0,1.5,.5,control).let{probeMap(it,DrivePoint(t,75.0,.5,1.5),control)}.copy(afterfireTrigger=i==39,shiftTrigger=i==39)
   if(i==39){old=state;oldRevision=probeRevision(state.inputControl)}
   val decision=gate.evaluate(state.inputControl,state.timeS,n)
   if(i==41){check(probeRevision(state.inputControl)>oldRevision);check(decision.clearTransients);check(!decision.allowEvents)}
   if(decision.clearTransients)renderer.clearTransientEvents()
   renderer.render(state.copy(afterfireTrigger=state.afterfireTrigger&&decision.allowEvents,shiftTrigger=state.shiftTrigger&&decision.allowEvents),960)
   if(i==40){check(afterfireIndex.getInt(renderer)>=0);check(activeShift.get(renderer)!=null)}
   if(i>=41){check(afterfireIndex.getInt(renderer)<0);check(activeShift.get(renderer)==null)}
  }
  val stats=renderer.mixStats();check(stats.hardClipFrames==0L&&stats.nonFiniteFrames==0L&&stats.aboveContractFrames==0L)
  println("coalesced invalid hidden; actual mapping revision persisted; pending afterfire and shift cleared before resumed render; $stats")
 }
}
