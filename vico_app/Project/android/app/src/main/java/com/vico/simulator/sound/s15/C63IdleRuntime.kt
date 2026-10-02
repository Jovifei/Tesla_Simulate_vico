package com.vico.simulator.sound.s15
import kotlin.math.*

/** Isolated causal conversion of S12 idle state. */
class C63IdleRuntime {
    class Snapshot internal constructor(internal val values:DoubleArray,internal val counters:LongArray,internal val arrays:List<DoubleArray>)
    fun snapshot()=Snapshot(doubleArrayOf(phase,texture),longArrayOf(lastEvent,rng,frame,index.toLong(),delayIndex.toLong()),
        listOf(combustion.save(),valve.save(),scheduled.copyOf(),accessoryDelay.copyOf(),crankDelay.copyOf(),gateDelay.copyOf()))
    fun restore(s:Snapshot){phase=s.values[0];texture=s.values[1];lastEvent=s.counters[0];rng=s.counters[1];frame=s.counters[2];index=s.counters[3].toInt();delayIndex=s.counters[4].toInt()
        combustion.load(s.arrays[0]);valve.load(s.arrays[1]);s.arrays[2].copyInto(scheduled);s.arrays[3].copyInto(accessoryDelay);s.arrays[4].copyInto(crankDelay);s.arrays[5].copyInto(gateDelay)}
    private class Ring(hz:Double,decay:Double) {
        private val r=exp(-1/(decay*48000));private val f=2*r*cos(2*PI*hz/48000);private val d=sin(2*PI*hz/48000)
        private var y1=0.0;private var y2=0.0
        fun save()=doubleArrayOf(y1,y2)
        fun load(s:DoubleArray){y1=s[0];y2=s[1]}
        fun step(x:Double):Double{val y=f*y1-r*r*y2+d*x;y2=y1;y1=y;return y}
    }
    private val combustion=Ring(520.0*.47,.012);private val valve=Ring(1300.0,.010)
    private var phase=0.0;private var lastEvent=-1L
    private val scheduled=DoubleArray(385);private var index=0
    private val accessoryDelay=DoubleArray(192);private val crankDelay=DoubleArray(192);private val gateDelay=DoubleArray(192)
    private var delayIndex=0;private var frame=0L
    private var rng=5900001L;private var texture=0.0
    fun sample(rpm:Double,load:Double,throttle:Double=0.0):Double {
        require(rpm.isFinite() && rpm>=0 && rpm<=7200 && load.isFinite() && load>=0 && load<=1)
        require(throttle.isFinite() && throttle>=0 && throttle<=1)
        phase+=rpm/(60*48000.0)
        val event=floor(phase*4).toLong()
        // T1 state correction: low RPM under propulsion is not idle.
        val idle=((1850-rpm)/850).coerceIn(0.0,1.0)*((.35-throttle)/.15).coerceIn(0.0,1.0)*((.50-load)/.30).coerceIn(0.0,1.0)
        if(event!=lastEvent && rpm>0) {
            val cycle=event.toDouble();val seed=5.9
            val variation=tanh((sin(cycle*12.9898+seed)*.45+sin(cycle*7.3137+seed*2.1)*.30+sin(cycle*23.7173+seed*.7)*.25)*.30*1.2)
            val jitter=((sin(cycle*78.233+seed*3)*.55+sin(cycle*137.51+seed*1.7)*.30+sin(cycle*43.91+seed*5.3)*.15)*4*48000/1000).roundToInt()
            // T1: fixed192-frame scheduling offset turns negative offline jitter causal.
            val offset=(max(0L,frame+jitter)-frame+192).toInt().coerceIn(0,384)
            scheduled[(index+offset)%scheduled.size]+=idle*(.55+.45*load)*(1+variation)
        }
        lastEvent=event
        val impulse=scheduled[index];scheduled[index]=0.0;index=(index+1)%scheduled.size
        rng=rng xor(rng shl 13);rng=rng xor(rng ushr 7);rng=rng xor(rng shl 17)
        val random=(rng ushr 11).toDouble()/9007199254740992.0*2-1
        texture+=(random-texture)/800
        val combustionValue=.060*combustion.step(impulse)*.895
        val accessory=.006*idle*(.55+load)*(sin(2*PI*phase*2.36)*.96+.28*sin(2*PI*phase*2.36*2)+texture*.04)*.85
        val valvetrain=.001*gateDelay[delayIndex]*valve.step(impulse)*.83
        val crank=.010*idle*(.65+.35*load)*sin(2*PI*phase*.5)*.94
        val delayedAccessory=accessoryDelay[delayIndex];val delayedCrank=crankDelay[delayIndex]
        accessoryDelay[delayIndex]=accessory;crankDelay[delayIndex]=crank;gateDelay[delayIndex]=idle
        delayIndex=(delayIndex+1)%192;frame++
        return combustionValue+delayedAccessory+valvetrain+delayedCrank
    }
}
