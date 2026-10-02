package com.vico.simulator.sound.s16
import kotlin.math.*
/** The only fit degrees of freedom are four immutable effective decay times. */
internal class C63BarkModes(decays:DoubleArray=doubleArrayOf(.045,.038,.034,.030)) {
    private val tau=decays.copyOf()
    private val original=doubleArrayOf(.045,.038,.034,.030)
    private val hz=doubleArrayOf(540.0,820.0,1100.0,1500.0)
    private val weights=doubleArrayOf(.50,.40,.42,.10)
    init {require(tau.size==4);require(tau.indices.all{tau[it].isFinite() && tau[it]>=original[it]*.25 && tau[it]<=original[it]})}
    private val radius=DoubleArray(4){exp(-1/(tau[it]*48000))}
    private val feedback=DoubleArray(4){2*radius[it]*cos(2*PI*hz[it]/48000)}
    private val drive=DoubleArray(4){sin(2*PI*hz[it]/48000)}
    private val y1=DoubleArray(4);private val y2=DoubleArray(4)
    class Snapshot internal constructor(internal val tau:DoubleArray,internal val y1:DoubleArray,internal val y2:DoubleArray)
    fun sample(input:Double):Double {
        require(input.isFinite());var result=0.0
        for(i in 0..3){val y=feedback[i]*y1[i]-radius[i]*radius[i]*y2[i]+drive[i]*input;y2[i]=y1[i];y1[i]=y;result+=weights[i]*y}
        return result
    }
    fun snapshot()=Snapshot(tau.copyOf(),y1.copyOf(),y2.copyOf())
    fun restore(snapshot:Snapshot) {
        require(snapshot.tau.contentEquals(tau) && snapshot.y1.size==4 && snapshot.y2.size==4)
        snapshot.y1.copyInto(y1);snapshot.y2.copyInto(y2)
    }
}
