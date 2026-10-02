package com.vico.simulator.sound.s15
import kotlin.math.*

/** Fixed TRI14/CAP1.2ms candidate. Area normalization is not energy normalization. */
class FinitePressureExcitation {
    private val l=DoubleArray(64);private val r=DoubleArray(64);private var index=0
    private val kernels=Array(58){n->if(n==0)DoubleArray(0) else DoubleArray(n){j->cdf((j+1.0)/n)-cdf(j.toDouble()/n)}}
    var left=0.0;private set
    var right=0.0;private set
    var injectedLeft=0.0;private set
    var injectedRight=0.0;private set
    var emittedLeft=0.0;private set
    var emittedRight=0.0;private set
    fun inject(bank:Int,area:Double,rpm:Double,overrideSamples:Int?=null){
        require((bank==0 || bank==1) && area.isFinite() && area>=0 && area<=2 && rpm.isFinite() && rpm>0 && rpm<=7200)
        val n=overrideSamples ?: max(1,floor(48000*min(14.0/(6*rpm),.0012)).toInt())
        require(n>=1 && n<=57)
        val queue=if(bank==0)l else r
        for(j in 0 until n)queue[(index+j)%64]+=area*kernels[n][j]
        if(bank==0)injectedLeft+=area else injectedRight+=area
    }
    fun step(){left=l[index];right=r[index];l[index]=0.0;r[index]=0.0;index=(index+1)%64;emittedLeft+=left;emittedRight+=right}
    fun remainingLeft()=l.sum()
    fun remainingRight()=r.sum()
    class Snapshot internal constructor(internal val l:DoubleArray,internal val r:DoubleArray,internal val index:Int,internal val totals:DoubleArray)
    fun snapshot()=Snapshot(l.copyOf(),r.copyOf(),index,doubleArrayOf(left,right,injectedLeft,injectedRight,emittedLeft,emittedRight))
    fun restore(s:Snapshot){s.l.copyInto(l);s.r.copyInto(r);index=s.index;left=s.totals[0];right=s.totals[1];injectedLeft=s.totals[2];injectedRight=s.totals[3];emittedLeft=s.totals[4];emittedRight=s.totals[5]}
    private fun cdf(u:Double)=if(u<=.5)2*u*u else 1-2*(1-u)*(1-u)
}
