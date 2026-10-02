package com.vico.simulator.sound.n2

class N2Renderer(private val source:N2Source=N2Source()) {
    enum class Branch { T,S,E,SE }

    fun render(branch:Branch,frames:Int,state:N2SoundState,event:Boolean):FloatArray {
        val out=when(branch){
            Branch.T -> FloatArray(frames)
            Branch.S,Branch.SE -> source.continuous(frames,state)
            Branch.E -> FloatArray(frames)
        }
        if(event && (branch==Branch.E || branch==Branch.SE)){
            val e=source.eventFIR(true)
            for(i in out.indices) out[i]+=e[i%e.size]
        }
        return out
    }
}
