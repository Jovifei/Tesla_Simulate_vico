package com.vico.simulator.sound.s16
/** Causal rectangular filter. No whole-clip or real-time normalization. */
internal class C63MechanicalTexture(private val scale:Double) {
    init {require(scale.isFinite() && scale>=0)}
    class Snapshot internal constructor(internal val ring:DoubleArray,internal val sum:Double,internal val cursor:Int,internal val rng:Long,internal val scale:Double)
    private val ring=DoubleArray(800)
    private var sum=0.0;private var cursor=0;private var rng=5900000L
    fun push(input:Double):Double {
        require(input.isFinite() && input>=-1 && input<=1)
        sum+=input-ring[cursor];ring[cursor]=input;cursor=(cursor+1)%ring.size
        return scale*sum/ring.size
    }
    fun sample():Double {
        rng=rng xor(rng shl 13);rng=rng xor(rng ushr 7);rng=rng xor(rng shl 17)
        return push((rng ushr 11).toDouble()/9007199254740992.0*2-1)
    }
    fun snapshot()=Snapshot(ring.copyOf(),sum,cursor,rng,scale)
    fun restore(snapshot:Snapshot) {
        require(snapshot.scale==scale && snapshot.ring.size==800 && snapshot.cursor in 0..799)
        snapshot.ring.copyInto(ring);sum=snapshot.sum;cursor=snapshot.cursor;rng=snapshot.rng
    }
}
