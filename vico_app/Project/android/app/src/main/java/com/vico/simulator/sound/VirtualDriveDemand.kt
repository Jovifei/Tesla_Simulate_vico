package com.vico.simulator.sound

import kotlin.math.abs
import kotlin.math.exp

/** Generic level-road engineering estimate, not a measured pedal, grade, drag or OEM map. */
data class VirtualDemandConfig(
    val rollingAccelerationMps2: Double = 0.13,
    val dragPerMetre: Double = 0.00028,
    val accelerationScaleMps2: Double = 3.0,
    val accelerationTimeConstantS: Double = 0.12,
    val maximumImuGapS: Double = 0.25,
    val parkedSpeedMps: Double = 0.30,
    val stationaryAccelerationMps2: Double = 0.10,
    val parkedDwellS: Double = 0.60,
    val decelerationThresholdMps2: Double = -0.20,
    val decelerationDwellS: Double = 0.15,
) {
    init {
        require(listOf(rollingAccelerationMps2, dragPerMetre, accelerationScaleMps2,
            accelerationTimeConstantS, maximumImuGapS, parkedSpeedMps,
            stationaryAccelerationMps2, parkedDwellS, decelerationThresholdMps2,
            decelerationDwellS).all { it.isFinite() })
        require(rollingAccelerationMps2 >= 0 && dragPerMetre >= 0 && accelerationScaleMps2 > 0)
        require(accelerationTimeConstantS > 0 && maximumImuGapS > 0 && parkedSpeedMps >= 0)
        require(stationaryAccelerationMps2 >= 0 && parkedDwellS > 0 && decelerationThresholdMps2 < -stationaryAccelerationMps2 && decelerationDwellS > 0)
    }
}

data class VirtualDemandInput(val epoch:Long,val usable:Boolean,val gpsNs:Long,val imuNs:Long,
    val speedMps:Double,val accelerationMps2:Double,val reportedSpeedUncertaintyMps:Double?=null)
data class VirtualDemandState(val demand:Double,val rawDemand:Double,val filteredAccelerationMps2:Double,
    val parked:Boolean,val sustainedDeceleration:Boolean,val freshImu:Boolean,val resumed:Boolean,
    val negativeAccelerationObserved:Boolean) {
    /** Asset coordinate, never a claim that the bank contains physical zero-load/coast audio. */
    val bankLoad:Double get()=0.32+0.60*demand
}

/** Confined to control owner. No publication-time clock advances this estimator. */
class VirtualDriveDemand(private val config:VirtualDemandConfig=VirtualDemandConfig()) {
    companion object { const val POLICY_ID = "real_virtual_drive_v1" }
    private var epoch:Long?=null
    private var lastGps=0L
    private var lastImu=0L
    private var acceptedRawAcceleration=Double.NaN
    private var acceptedSpeed=Double.NaN
    private var acceptedUncertainty:Double?=null
    private var acceleration=0.0
    private var stationarySince=0L
    private var decelerationSince=0L
    private var valid=false
    private var previous:VirtualDemandState?=null
    fun invalidate(){valid=false;stationarySince=0;decelerationSince=0;previous=null}
    fun update(input:VirtualDemandInput):VirtualDemandState? {
        if(epoch!=null && input.epoch<epoch!!)return null
        if(!input.usable || input.epoch<0 || input.gpsNs<=0 || input.imuNs<=0 ||
            !input.speedMps.isFinite() || input.speedMps<0 || !input.accelerationMps2.isFinite() || input.reportedSpeedUncertaintyMps?.let{!it.isFinite() || it<0.0}==true) {
            invalidate();return null
        }
        val sameEpoch=epoch==input.epoch
        if(sameEpoch && (input.gpsNs<lastGps || input.imuNs<lastImu))return null
        if(sameEpoch && (input.imuNs==lastImu && input.accelerationMps2!=acceptedRawAcceleration ||
            input.gpsNs==lastGps && (input.speedMps!=acceptedSpeed || input.reportedSpeedUncertaintyMps!=acceptedUncertainty))) { invalidate();return null }
        val fresh=!sameEpoch || input.imuNs>lastImu
        val gap=if(sameEpoch && lastImu>0)(input.imuNs-lastImu)/1e9 else 0.0
        val resumed=!valid || !sameEpoch || gap>config.maximumImuGapS+1e-9
        if(!fresh && !resumed && input.gpsNs==lastGps)return previous?.copy(freshImu=false,resumed=false)
        if(resumed){acceleration=input.accelerationMps2;stationarySince=0;decelerationSince=0}
        else if(fresh){acceleration+=(1-exp(-gap/config.accelerationTimeConstantS))*(input.accelerationMps2-acceleration)}
        val stationary=input.speedMps<=config.parkedSpeedMps && abs(input.accelerationMps2)<=config.stationaryAccelerationMps2
        // Any contrary observation clears the condition immediately, even a GPS-only update.
        if(!stationary)stationarySince=0
        if(input.accelerationMps2>config.decelerationThresholdMps2)decelerationSince=0
        if(fresh || resumed){
            if(stationary && stationarySince==0L)stationarySince=input.imuNs
            if(input.accelerationMps2<=config.decelerationThresholdMps2 && decelerationSince==0L)decelerationSince=input.imuNs
        }
        val parked=stationarySince>0 && (input.imuNs-stationarySince)/1e9+1e-9>=config.parkedDwellS
        val decel=decelerationSince>0 && (input.imuNs-decelerationSince)/1e9+1e-9>=config.decelerationDwellS
        val road=config.rollingAccelerationMps2+config.dragPerMetre*input.speedMps*input.speedMps
        val rawUnclamped=(input.accelerationMps2+road)/config.accelerationScaleMps2
        val filteredUnclamped=(acceleration+road)/config.accelerationScaleMps2
        if(!road.isFinite() || !acceleration.isFinite() || !rawUnclamped.isFinite() || !filteredUnclamped.isFinite()) { invalidate();return null }
        val raw=rawUnclamped.coerceIn(0.0,1.0)
        val demand=if(parked)0.0 else filteredUnclamped.coerceIn(0.0,1.0)
        epoch=input.epoch;lastGps=input.gpsNs;lastImu=input.imuNs;acceptedRawAcceleration=input.accelerationMps2;acceptedSpeed=input.speedMps;acceptedUncertainty=input.reportedSpeedUncertaintyMps;valid=true
        return VirtualDemandState(demand,raw,acceleration,parked,decel,fresh,resumed,input.accelerationMps2<=config.decelerationThresholdMps2).also{previous=it}
    }
}
