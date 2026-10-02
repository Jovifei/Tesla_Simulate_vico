package com.vico.simulator.sound.n2

import kotlin.math.PI
import kotlin.math.sin
import kotlin.math.max

class N2Source(private val profile:N2Profile=N2Profile()) {
    private var phase=0.0
    private var occurrenceSeed=profile.seed
    private var responseSeed=profile.seed xor 0x55AA

    fun snapshot()=N2Snapshot(phase,occurrenceSeed,responseSeed)
    fun restore(s:N2Snapshot){phase=s.phase; occurrenceSeed=s.occurrenceSeed; responseSeed=s.responseSeed}

    fun continuous(frames:Int,state:N2SoundState):FloatArray {
        val out=FloatArray(frames)
        val rpmHz=max(1.0,state.rpm/60.0)
        val gain=(0.15+0.55*state.load+0.2*state.throttle).coerceIn(0.0,1.0)
        for(i in out.indices){
            var x=0.0
            for(k in 1..profile.basisCount){
                x += (0.01/k)*sin(phase + 2.0*PI*rpmHz*k*i/profile.sampleRate)
            }
            out[i]=(x*gain).toFloat()
            phase += 2.0*PI*rpmHz/profile.sampleRate
            if(phase>2*PI) phase-=2*PI
        }
        return out
    }

    fun eventFIR(trigger:Boolean):FloatArray {
        if(!trigger) return FloatArray(profile.eventLength)
        val out=FloatArray(profile.eventLength)
        var x=responseSeed
        for(i in out.indices){
            x=x*6364136223846793005L+1442695040888963407L
            val impulse=if(i<64) kotlin.math.exp(-i/18.0).toFloat() else 0f
            out[i]=impulse*(((x ushr 40)&255)/255f)
        }
        responseSeed=x
        return out
    }
}
