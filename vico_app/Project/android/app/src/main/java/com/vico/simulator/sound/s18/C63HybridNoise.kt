package com.vico.simulator.sound.s18
import kotlin.math.*

/** Four independent broad bands, normalized once from their impulse energies. */
internal class C63HybridNoise(seed:Long,weights:DoubleArray) {
    private val gains=weights.copyOf()
    init {require(seed!=0L && gains.size==4 && gains.all{it.isFinite() && it>=0} && abs(gains.sumOf{it*it}-1)<1e-8)}
    private val identity=seed.toString()+"|"+gains.joinToString(",")
    private val rng=LongArray(4){seed xor (-7046029254386353131L*(it+1))}
    private class Band(hz:Double) {
        private val w=2*PI*hz/48000;private val alpha=sin(w)/(2*.7071067811865476)
        private val b0=alpha/(1+alpha);private val b2=-b0
        private val a1=-2*cos(w)/(1+alpha);private val a2=(1-alpha)/(1+alpha)
        private var z1=0.0;private var z2=0.0
        private fun raw(x:Double):Double {val y=b0*x+z1;z1=-a1*y+z2;z2=b2*x-a2*y;return y}
        private val normalization=run {
            var energy=0.0;repeat(4096){n->val y=raw(if(n==0)1.0 else 0.0);energy+=y*y}
            z1=0.0;z2=0.0;1/sqrt(energy)
        }
        fun sample(x:Double)=raw(x)*normalization
        fun state()=doubleArrayOf(z1,z2)
        fun restore(s:DoubleArray){z1=s[0];z2=s[1]}
    }
    private val filters=doubleArrayOf(315.0,800.0,2000.0,5000.0).map{Band(it)}
    val lastBands=DoubleArray(4)
    fun sample():Double {
        var result=0.0
        for(i in 0..3){var x=rng[i];x=x xor(x shl 13);x=x xor(x ushr 7);x=x xor(x shl 17);rng[i]=x
            val white=(((x*2685821657736338717L) ushr 11).toDouble()/9007199254740992.0*2-1)*sqrt(3.0)
            lastBands[i]=filters[i].sample(white);result+=gains[i]*lastBands[i]
        }
        check(result.isFinite());return result
    }
    class Snapshot internal constructor(internal val identity:String,internal val rng:LongArray,internal val filters:List<DoubleArray>,internal val bands:DoubleArray)
    fun snapshot()=Snapshot(identity,rng.copyOf(),filters.map{it.state()},lastBands.copyOf())
    fun restore(s:Snapshot){require(s.identity==identity && s.rng.size==4 && s.filters.size==4 && s.bands.size==4 && s.bands.all{it.isFinite()} && s.filters.all{it.size==2 && it.all{v->v.isFinite()}})
        s.rng.copyInto(rng);s.bands.copyInto(lastBands);filters.indices.forEach{filters[it].restore(s.filters[it])}}
}
