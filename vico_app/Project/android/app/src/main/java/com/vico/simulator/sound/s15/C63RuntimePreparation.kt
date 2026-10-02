package com.vico.simulator.sound.s15

import com.vico.simulator.sound.SoundState

/** Off-thread JIT/table warmup. The instance is discarded, never used for playback. */
internal object C63RuntimePreparation {
    fun warmup(cancelled:()->Boolean={false}) {
        val discarded=C63RuntimeRenderer(fixedHeadroom=true)
        repeat(300){n->
            if(cancelled())return
            val closed=n>=200
            discarded.render(SoundState(n*.02,4000.0,4000.0/15,.4,.4,floatArrayOf(),false,
                if(closed).05 else .4,if(closed).05 else .4,shiftTrigger=n==150),960)
        }
    }
}
