package com.vico.simulator.sound
import kotlin.math.*
fun main(){
 println("profile,rolling,drag,scale,c0,hz,speed,initial_high,gear,demand,rpm,late_shifts,recovery_events")
 var rows=0;var failed=0
 for((name,spec) in bankSpecs()) for(a0 in listOf(.12,.13,.1373)) for(b in listOf(.000241,.00028,.000348,.0006)) for(scale in listOf(2.0,3.0,4.0)) for(c0 in listOf(.3,.4,.5)) for(hz in listOf(10,20,50)) for(v in listOf(0.0,20.0,40.0,70.0,75.0,100.0,144.0)) for(high in listOf(false,true)){
  val demand=VirtualDriveDemand(VirtualDemandConfig(rollingAccelerationMps2=a0,dragPerMetre=b,accelerationScaleMps2=scale))
  val gear=VirtualCruiseGear(spec,VirtualCruiseConfig(lowDemandShiftFraction=c0))
  gear.update(1.0,if(high)144.0 else 0.0,.1,true,true,!high,0.0)
  var late=0;var recovery=0;var g=1;var d=0.0
  for(i in 0..(hz*20)){
   val t=2.0+i.toDouble()/hz;val ns=(t*1e9).toLong();val gps=(floor(t)*1e9).toLong()
   if(i==hz*10){demand.invalidate();gear.invalidate()}
   val ds=demand.update(VirtualDemandInput(if(i<hz*10)1 else 2,true,gps,ns,v/3.6,.08*sin(t*2*PI/.7),0.0))!!
   val gs=gear.update(t,v,ds.demand,ds.freshImu,ds.resumed,ds.parked,0.0)
   if(i>hz*5&&gs.changed)late++
   if(ds.resumed&&gs.changed)recovery++
   g=gs.gear;d=ds.demand
  }
  val rpm=max(spec.idleRpm,v/3.6/(2*PI*spec.wheelRadiusM)*60*spec.finalDrive*spec.gearRatios[g-1])
  println("$name,$a0,$b,$scale,$c0,$hz,$v,$high,$g,$d,$rpm,$late,$recovery")
  rows++;if(late!=0||recovery!=0)failed++
 }
 System.err.println("grid_rows=$rows late_hunting_or_recovery_cases=$failed")
 check(failed==0)
}
