package com.vico.simulator.sound
import kotlin.math.PI
import kotlin.math.max
import kotlin.math.min

/** Versioned virtual strategy candidates, not vehicle-specific transmission calibration. */
data class VirtualCruiseConfig(val lowDemandShiftFraction:Double=.40,val shiftDwellS:Double=.40,
 val minimumShiftIntervalS:Double=.80,val minimumPostShiftIdleMultiple:Double=1.40,
 val lowerGearRedlineFraction:Double=.98,val declaredDemandNoise:Double=.10,
 val unverifiedSpeedBufferMps:Double=2.0) {
 init {require(listOf(lowDemandShiftFraction,shiftDwellS,minimumShiftIntervalS,minimumPostShiftIdleMultiple,lowerGearRedlineFraction,declaredDemandNoise,unverifiedSpeedBufferMps).all{it.isFinite()});require(lowDemandShiftFraction in .1..1.0 && shiftDwellS>0 && minimumShiftIntervalS>=shiftDwellS && minimumPostShiftIdleMultiple>=1 && lowerGearRedlineFraction in .5..1.0 && declaredDemandNoise in 0.0..0.5 && unverifiedSpeedBufferMps>=0.0)}
}
data class VirtualGearState(val gear:Int,val changed:Boolean,val upshiftRpm:Double)
class VirtualCruiseGear(private val spec:MatlabPowertrainSpec,private val config:VirtualCruiseConfig=VirtualCruiseConfig()) {
 private var gear=1;private var initialized=false;private var lastTime=Double.NaN
 private var lastShift=Double.NEGATIVE_INFINITY;private var direction=0;private var since=Double.NaN
 init {
  require(spec.gearRatios.isNotEmpty() && spec.gearRatios.all{it.isFinite()&&it>0})
  require(spec.gearRatios.toList().zipWithNext().all{it.first>it.second})
  require(spec.idleRpm>0 && spec.shiftRpm>spec.idleRpm && spec.redlineRpm>=spec.shiftRpm && spec.downshiftRatio in 0.0..0.99)
  // Algebraic immunity to the declared bounded demand noise, not merely delayed hunting.
  for(d in listOf(0.0,config.declaredDemandNoise,1.0-config.declaredDemandNoise,1.0)){require(spec.downshiftRatio*upshiftRpm(min(1.0,d+config.declaredDemandNoise))<upshiftRpm(max(0.0,d-config.declaredDemandNoise)))}
 }
 fun upshiftRpm(d:Double)=spec.idleRpm+(spec.shiftRpm-spec.idleRpm)*(config.lowDemandShiftFraction+(1-config.lowDemandShiftFraction)*d.coerceIn(0.0,1.0))
 private fun rpmPerKmh(g:Int)=spec.gearRatios[g-1]*spec.finalDrive*60/(3.6*2*PI*spec.wheelRadiusM)
 private fun upSpeed(g:Int,d:Double)=upshiftRpm(d)/rpmPerKmh(g)
 private fun requested(speed:Double,d:Double,bufferMps:Double):Int {
  val low=max(0.0,speed-3.6*bufferMps);val high=speed+3.6*bufferMps
  if(gear<spec.gearRatios.size && low>=upSpeed(gear,d) && low*rpmPerKmh(gear+1)>=spec.idleRpm*config.minimumPostShiftIdleMultiple)return 1
  if(gear>1 && high<=spec.downshiftRatio*upSpeed(gear-1,d) && high*rpmPerKmh(gear-1)<spec.redlineRpm*config.lowerGearRedlineFraction)return -1
  return 0
 }
 fun invalidate(){initialized=false;direction=0;since=Double.NaN}
 fun update(timeS:Double,speedKmh:Double,demand:Double,freshImu:Boolean,resumed:Boolean,parked:Boolean,reportedSpeedUncertaintyMps:Double?=null):VirtualGearState {
  require(timeS.isFinite()&&timeS>=0&&speedKmh.isFinite()&&speedKmh>=0&&demand.isFinite()&&demand in 0.0..1.0)
  require(reportedSpeedUncertaintyMps?.let{it.isFinite()&&it>=0.0}!=false)
  val buffer=reportedSpeedUncertaintyMps ?: config.unverifiedSpeedBufferMps
  val u=upshiftRpm(demand)
  if(!initialized||resumed){
   // Select a holding gear silently on a new trusted segment, never fabricate transition events.
   if(parked)gear=1 else for(i in spec.gearRatios.indices){val r=requested(speedKmh,demand,buffer);if(r==0)break;gear+=r}
   initialized=true;direction=0;since=Double.NaN;lastTime=timeS;lastShift=timeS
   return VirtualGearState(gear,false,u)
  }
  if(!freshImu || timeS<=lastTime)return VirtualGearState(gear,false,u)
  lastTime=timeS
  if(parked){gear=1;direction=0;since=Double.NaN;lastShift=timeS;return VirtualGearState(gear,false,u)}
  val r=requested(speedKmh,demand,buffer)
  if(r!=direction){direction=r;since=timeS}
  if(r==0){since=Double.NaN;return VirtualGearState(gear,false,u)}
  if(timeS-since+1e-9<config.shiftDwellS || timeS-lastShift+1e-9<max(config.minimumShiftIntervalS,spec.totalShiftTimeS))return VirtualGearState(gear,false,u)
  gear+=r;lastShift=timeS;direction=0;since=Double.NaN
  return VirtualGearState(gear,true,u)
 }
}
