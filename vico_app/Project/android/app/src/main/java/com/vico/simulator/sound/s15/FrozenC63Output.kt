package com.vico.simulator.sound.s15
import kotlin.math.*

/** Original output math only; no new EQ tuning or normalization. */
class FrozenC63Output {
    private class FirstOrder(hz:Double,high:Boolean) {
        private val k=tan(PI*hz/48000)
        private val b0=if(high)1/(1+k) else k/(1+k)
        private val b1=if(high)-b0 else b0
        private val a1=(k-1)/(k+1)
        private var z=0.0
        fun save()=z
        fun load(state:Double){z=state}
        fun step(x:Double):Double{val y=b0*x+z;z=b1*x-a1*y;return y}
    }
    private val low=FirstOrder(220.0,false);private val high=FirstOrder(3200.0,true);private val dc=FirstOrder(20.0,true)
    private val delay=DoubleArray(20);private var index=0
    private var x0=0.0;private var x1=0.0
    private val dt=1.0/48000
    private val a10=-6.4359409190371978e8;private val a11=-52275.601750547037
    private val c0=-6.4359409190371978e8;private val c1=-6267.06783369803
    private val determinant=1-dt*a11/2-dt*dt*a10/4
    class Snapshot internal constructor(internal val states:DoubleArray,internal val delay:DoubleArray,internal val index:Int)
    fun snapshot()=Snapshot(doubleArrayOf(low.save(),high.save(),dc.save(),x0,x1),delay.copyOf(),index)
    fun restore(s:Snapshot){low.load(s.states[0]);high.load(s.states[1]);dc.load(s.states[2]);x0=s.states[3];x1=s.states[4];s.delay.copyInto(delay);index=s.index}
    fun sample(value:Double):Double {
        require(value.isFinite())
        var input=value+(10.0.pow(18.0/20)-1)*low.step(value)
        input+=(10.0.pow(-17.0/20)-1)*high.step(input)
        input=dc.step(input)
        val outgoing=delay[index]*.98*.97;delay[index]=input;index=(index+1)%20
        val rhs0=x0+dt*x1/2
        val rhs1=dt*a10*x0/2+(1+dt*a11/2)*x1+dt*outgoing
        x0=((1-dt*a11/2)*rhs0+dt*rhs1/2)/determinant
        x1=(dt*a10*rhs0/2+rhs1)/determinant
        val result=(outgoing+c0*x0+c1*x1)*3.7075542301539652
        check(result.isFinite());return result
    }
}
