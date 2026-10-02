package com.vico.simulator.sound
import com.vico.simulator.sound.s15.*
import org.junit.Assert.*
import org.junit.Test

class C63HeadroomTest {
    private fun s(t:Double)=SoundState(t,2050.0,2050.0/60*4,1.0,1.0,floatArrayOf(),false,1.0,1.0)
    @Test fun c_is_exact_single_fixed_scalar_times_complete_a_without_preclip() {
        val a=C63RuntimeRenderer(true,false);val c=C63RuntimeRenderer(false,false,true)
        repeat(150){n->val aa=a.render(s(n*.02),960);val cc=c.render(s(n*.02),960)
            for(i in cc.indices)assertEquals((aa[i]*C63HeadroomProfile.SCALAR).toFloat(),cc[i],1e-6f)
        }
        assertTrue(a.peak>1);assertTrue(c.peak<=.8413951416451951)
    }
    @Test(expected=IllegalArgumentException::class) fun rejected_b_cannot_be_rescaled_as_c() {
        C63RuntimeRenderer(false,true,true)
    }
}
