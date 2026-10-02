package com.vico.simulator.sound.s17
internal object C63ModalSpectrum {
    private fun power(samples:FloatArray,hz:Double):Double {
        require(samples.isNotEmpty() && hz.isFinite() && hz in 1.0..23999.0)
        val omega=2*Math.PI*hz/48000;val coefficient=2*kotlin.math.cos(omega);var a=0.0;var b=0.0
        for(sample in samples){val next=sample.toDouble()+coefficient*a-b;b=a;a=next}
        val real=a-b*kotlin.math.cos(omega);val imaginary=b*kotlin.math.sin(omega)
        val size=samples.size.toDouble()
        return (real*real+imaginary*imaginary)/(size*size)
    }
    fun linePower(samples:FloatArray,hz:Double)=power(samples,hz)
    fun prominence(samples:FloatArray,hz:Double):Double {
        require(hz in 81.0..23919.0)
        val neighbors=doubleArrayOf(-80.0,-60.0,-40.0,40.0,60.0,80.0).map{power(samples,hz+it)}
        return 10*kotlin.math.log10(maxOf(power(samples,hz),1e-30)/maxOf(neighbors.average(),1e-30))
    }
}
