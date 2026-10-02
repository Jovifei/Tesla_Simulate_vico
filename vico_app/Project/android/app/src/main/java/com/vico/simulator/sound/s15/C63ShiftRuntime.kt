package com.vico.simulator.sound.s15
import kotlin.math.*
class C63ShiftRuntime {
    class Snapshot internal constructor(internal val age:Long,internal val z1:Double,internal val z2:Double)
    fun snapshot()=Snapshot(age,z1,z2)
    fun restore(s:Snapshot){age=s.age;z1=s.z1;z2=s.z2}
    private var age=Long.MAX_VALUE;private var z1=0.0;private var z2=0.0
    private val k=tan(PI*350/48000);private val den=1+sqrt(2.0)*k+k*k
    private val b0=k*k/den;private val b1=2*b0;private val b2=b0
    private val a1=2*(k*k-1)/den;private val a2=(1-sqrt(2.0)*k+k*k)/den
    fun sample(input:Double,event:Boolean):Double {
        require(input.isFinite())
        if(event)age=0
        val seconds=if(age==Long.MAX_VALUE)1.0 else age/48000.0
        // T1: torque dip starts at causal event arrival, not25ms before it.
        val envelope=when {
            seconds<.04 -> 1-.78*seconds/.04
            seconds<.10 -> .22+.78*(seconds-.04)/.06
            else -> 1.0
        }
        val impulse=if(event).85*.50 else 0.0
        val impact=b0*impulse+z1;z1=b1*impulse-a1*impact+z2;z2=b2*impulse-a2*impact
        val t=seconds-.040
        val boom=if(t>=0 && t<.14).85*.38*sin(2*PI*70*t)*exp(-6*t/.14)*(1-t/.14) else 0.0
        if(age!=Long.MAX_VALUE)age++
        return input*envelope+impact+boom
    }
}
