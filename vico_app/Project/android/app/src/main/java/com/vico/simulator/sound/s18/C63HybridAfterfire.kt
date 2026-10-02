package com.vico.simulator.sound.s18
import com.vico.simulator.sound.s17.C63AR2AfterfireRuntime
import kotlin.math.*

/** Frozen occurrence logic plus a separately seeded synthetic finite pressure response. */
internal class C63HybridAfterfire(profile:C63HybridProfile) {
    private val identity=profile.identity
    private val occurrence=C63AR2AfterfireRuntime(profile.eventSeed,0.0)
    private var rng=profile.responseSeed
    var lastAngle=0.0;private set
    var legacySignal=0.0;private set
    val lastImpulse get()=occurrence.lastImpulse
    val events get()=occurrence.events
    private val response=C63FiniteResponseSource(
        profile.afterfirePressure.map{it*profile.eventScale*sqrt(1-profile.eventNoiseFraction)}.toDoubleArray(),
        profile.afterfireNoiseA.map{it*profile.eventScale*sqrt(profile.eventNoiseFraction)}.toDoubleArray(),
        profile.afterfireNoiseB.map{it*profile.eventScale*sqrt(profile.eventNoiseFraction)}.toDoubleArray())
    val pendingFrames get()=response.pendingFrames
    val thermalState get()=occurrence.thermalState
    val episodeAgeFrames get()=occurrence.episodeAgeFrames
    fun observation()=occurrence.observation()
    fun sample(rpm:Double,load:Double,throttle:Double,opportunity:Boolean,validInput:Boolean=true):Double {
        // The frozen helper's former sinusoidal response is calculated but never mixed here.
        legacySignal=occurrence.sample(rpm,load,throttle,opportunity,validInput)
        if(occurrence.lastImpulse>0) {
            rng=rng xor(rng shl 13);rng=rng xor(rng ushr 7);rng=rng xor(rng shl 17)
            val angle=2*PI*((rng*2685821657736338717L) ushr 11).toDouble()/9007199254740992.0
            lastAngle=angle
            response.inject(occurrence.distinctImpulseFrames-1,0,occurrence.lastImpulse,cos(angle),sin(angle))
        }
        response.step();return response.left+response.right
    }
    class Snapshot internal constructor(internal val identity:String,internal val occurrence:C63AR2AfterfireRuntime.Snapshot,
        internal val response:C63FiniteResponseSource.Snapshot,internal val rng:Long,internal val angle:Double,internal val legacySignal:Double)
    fun snapshot()=Snapshot(identity,occurrence.snapshot(),response.snapshot(),rng,lastAngle,legacySignal)
    fun restore(s:Snapshot){require(s.identity==identity && s.angle.isFinite() && s.legacySignal.isFinite());occurrence.restore(s.occurrence);response.restore(s.response);rng=s.rng;lastAngle=s.angle;legacySignal=s.legacySignal}
}
